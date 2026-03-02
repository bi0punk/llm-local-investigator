from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from .shell import has_cmd, maybe_run
from .utils import ensure_dir, now_iso


def base_artifacts(since: str, until: str, include_previous_boot: bool = True) -> Dict[str, str]:
    artifacts = {
        "journal": maybe_run(f"journalctl --since '{since}' --until '{until}' --no-pager -o short-iso", timeout=60, required_binary="journalctl"),
        "kernel_journal": maybe_run(f"journalctl -k --since '{since}' --until '{until}' --no-pager -o short-iso", timeout=60, required_binary="journalctl"),
        "priority_errors": maybe_run(f"journalctl -p 0..4 --since '{since}' --until '{until}' --no-pager -o short-iso", timeout=60, required_binary="journalctl"),
        "dmesg_tail": maybe_run("dmesg -T | tail -n 400", timeout=20, required_binary="dmesg"),
        "last_reboots": maybe_run("last -x -F | head -n 60", timeout=20, required_binary="last"),
        "who_boot": maybe_run("who -b", timeout=10, required_binary="who"),
        "uptime": maybe_run("uptime", timeout=10, required_binary="uptime"),
        "free": maybe_run("free -m", timeout=10, required_binary="free"),
        "top_mem": maybe_run("ps -eo pid,ppid,user,comm,%mem,%cpu --sort=-%mem | head -n 25", timeout=10, required_binary="ps"),
        "top_cpu": maybe_run("ps -eo pid,ppid,user,comm,%cpu,%mem --sort=-%cpu | head -n 25", timeout=10, required_binary="ps"),
        "df": maybe_run("df -h", timeout=10, required_binary="df"),
        "lsblk": maybe_run("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT", timeout=10, required_binary="lsblk"),
        "mount": maybe_run("mount | tail -n 40", timeout=10, required_binary="mount"),
        "failed_units": maybe_run("systemctl --failed --no-pager --plain", timeout=20, required_binary="systemctl"),
        "sensors": maybe_run("sensors", timeout=10, required_binary="sensors"),
    }
    if include_previous_boot:
        artifacts["prev_boot_kernel_tail"] = maybe_run("journalctl -k -b -1 -n 400 --no-pager -o short-iso", timeout=60, required_binary="journalctl")
        artifacts["prev_boot_errors"] = maybe_run("journalctl -p 0..4 -b -1 -n 400 --no-pager -o short-iso", timeout=60, required_binary="journalctl")
    return artifacts


def decide_extra_profiles(signals: Dict[str, List[str]]) -> List[str]:
    profiles = set()
    if not signals:
        profiles.update({"disk", "memory", "thermal"})
    if "disk_or_fs" in signals:
        profiles.add("disk")
    if "oom_killer" in signals:
        profiles.add("memory")
    if "thermal" in signals:
        profiles.add("thermal")
    if "gpu_hang" in signals:
        profiles.add("gpu")
    if "kernel_panic" in signals or "soft_or_hard_lockup" in signals:
        profiles.add("kernel")
    return sorted(profiles)


def extra_artifacts(profiles: List[str]) -> Dict[str, str]:
    artifacts: Dict[str, str] = {}

    if "disk" in profiles:
        artifacts["smartctl_scan"] = maybe_run("smartctl --scan-open", timeout=20, required_binary="smartctl")
        artifacts["nvme_list"] = maybe_run("nvme list", timeout=20, required_binary="nvme")
        artifacts["disk_errors_grep"] = maybe_run(
            "bash -lc \"journalctl --no-pager -o short-iso | grep -Ei 'nvme|I/O error|EXT4-fs error|XFS|Buffer I/O|blk_update_request|ata[0-9]+' | tail -n 200\"",
            timeout=60,
            required_binary="journalctl",
        )
        lsblk_out = maybe_run("lsblk -dn -o NAME,TYPE", timeout=10, required_binary="lsblk")
        for line in lsblk_out.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            name, devtype = parts
            if devtype != "disk":
                continue
            artifacts[f"smartctl_{name}"] = maybe_run(f"smartctl -H -A /dev/{name}", timeout=30, required_binary="smartctl")
            if has_cmd("nvme") and name.startswith("nvme"):
                artifacts[f"nvme_smart_{name}"] = maybe_run(f"nvme smart-log /dev/{name}", timeout=20, required_binary="nvme")

    if "memory" in profiles:
        artifacts["meminfo"] = maybe_run("cat /proc/meminfo | head -n 80", timeout=10)
        artifacts["vmstat"] = maybe_run("vmstat 1 5", timeout=10, required_binary="vmstat")
        artifacts["oom_grep"] = maybe_run(
            "bash -lc \"journalctl --no-pager -o short-iso | grep -Ei 'oom-killer|Out of memory|Killed process' | tail -n 200\"",
            timeout=60,
            required_binary="journalctl",
        )

    if "thermal" in profiles:
        artifacts["thermal_zone"] = maybe_run(
            r"""python3 - <<'PY'
import glob
for f in glob.glob('/sys/class/thermal/thermal_zone*/temp'):
    try:
        print(f"{f}={open(f).read().strip()}")
    except Exception as exc:
        print(f"{f}=ERROR:{exc}")
PY""",
            timeout=20,
        )
        artifacts["thermal_grep"] = maybe_run(
            "bash -lc \"journalctl --no-pager -o short-iso | grep -Ei 'thermal|throttl|overheat|temperature' | tail -n 200\"",
            timeout=60,
            required_binary="journalctl",
        )

    if "gpu" in profiles:
        artifacts["gpu_modules"] = maybe_run("lsmod | grep -Ei 'nvidia|amdgpu|i915|nouveau'", timeout=10, required_binary="lsmod")
        artifacts["gpu_grep"] = maybe_run(
            "bash -lc \"journalctl --no-pager -o short-iso | grep -Ei 'amdgpu|i915|nouveau|NVRM|GPU HANG|Xid' | tail -n 200\"",
            timeout=60,
            required_binary="journalctl",
        )

    if "kernel" in profiles:
        artifacts["kernel_errors_recent"] = maybe_run("journalctl -k -p 0..4 -n 300 --no-pager -o short-iso", timeout=60, required_binary="journalctl")
        artifacts["hung_tasks"] = maybe_run(
            "bash -lc \"journalctl --no-pager -o short-iso | grep -Ei 'blocked for more than|soft lockup|hard LOCKUP|BUG:' | tail -n 200\"",
            timeout=60,
            required_binary="journalctl",
        )

    return artifacts


def capture_snapshot_once(snapshot_dir: Path) -> Dict[str, Any]:
    snapshot_dir = ensure_dir(snapshot_dir)
    data = {
        "captured_at": now_iso(),
        "uptime": maybe_run("uptime", timeout=10, required_binary="uptime"),
        "free": maybe_run("free -m", timeout=10, required_binary="free"),
        "df": maybe_run("df -h", timeout=10, required_binary="df"),
        "top_cpu": maybe_run("ps -eo pid,ppid,user,comm,%cpu,%mem --sort=-%cpu | head -n 15", timeout=10, required_binary="ps"),
        "top_mem": maybe_run("ps -eo pid,ppid,user,comm,%mem,%cpu --sort=-%mem | head -n 15", timeout=10, required_binary="ps"),
        "dmesg_tail": maybe_run("dmesg -T | tail -n 60", timeout=15, required_binary="dmesg"),
        "sensors": maybe_run("sensors", timeout=10, required_binary="sensors"),
    }
    day_file = snapshot_dir / (datetime.utcnow().strftime("%Y%m%d") + ".jsonl")
    with day_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False) + "\n")
    data["source_file"] = str(day_file)
    return data


def load_snapshots_around(snapshot_dir: Path, incident_ts: str, minutes: int, max_rows: int) -> Dict[str, Any]:
    snapshot_dir = Path(snapshot_dir)
    if not snapshot_dir.exists():
        return {"rows": [], "summary": "snapshot_dir does not exist"}

    incident = datetime.strptime(incident_ts, "%Y-%m-%d %H:%M:%S")
    start = incident - timedelta(minutes=minutes)
    end = incident + timedelta(minutes=minutes)
    rows: List[Dict[str, Any]] = []

    for path in sorted(snapshot_dir.glob("*.jsonl")):
        try:
            contents = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in contents:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                ts = obj.get("captured_at", "")
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                if start <= dt <= end:
                    rows.append(obj)
            except Exception:
                continue

    rows = rows[:max_rows]
    return {
        "rows": rows,
        "summary": f"Loaded {len(rows)} snapshots in ±{minutes} minute window",
    }
