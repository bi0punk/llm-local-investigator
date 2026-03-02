from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

PATTERNS: Dict[str, Tuple[str, int, str]] = {
    "oom_killer": (r"(Out of memory|oom-killer|Killed process \d+)", 9, "memory"),
    "soft_or_hard_lockup": (
        r"(watchdog: BUG: soft lockup|watchdog: BUG: hard LOCKUP|soft lockup|hard LOCKUP|blocked for more than \d+ seconds)",
        10,
        "kernel",
    ),
    "disk_or_fs": (
        r"(I/O error|blk_update_request|Buffer I/O error|EXT4-fs error|XFS.*error|nvme.*reset|ata\d+: hard resetting link)",
        8,
        "disk",
    ),
    "thermal": (r"(thermal|throttl|overheat|Temperature above threshold)", 7, "thermal"),
    "gpu_hang": (r"(amdgpu.*timeout|i915.*GPU HANG|NVRM: Xid|nouveau.*fifo|GPU HANG)", 8, "gpu"),
    "kernel_panic": (r"(Kernel panic|Call Trace:|BUG: unable to handle kernel)", 10, "kernel"),
    "reboot_power_loss": (r"(unexpected shutdown|reboot|Power key pressed|watchdog did not stop)", 4, "power"),
}


def evaluate_rules(artifacts: Dict[str, str], max_lines: int = 12) -> Dict[str, Any]:
    text = "\n\n".join(artifacts.values())
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    signals: Dict[str, List[str]] = {}
    category_scores: Dict[str, int] = defaultdict(int)

    for name, (pattern, weight, category) in PATTERNS.items():
        rx = re.compile(pattern, re.IGNORECASE)
        hits = [ln for ln in lines if rx.search(ln)]
        if hits:
            signals[name] = hits[:max_lines]
            category_scores[category] += weight * min(len(hits), 3)

    ranked = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    strongest_signal = ranked[0][0] if ranked else "unknown"
    return {
        "signals": signals,
        "category_scores": dict(category_scores),
        "ranked_categories": ranked,
        "has_high_signal": any(score >= 10 for _, score in ranked),
        "strongest_signal": strongest_signal,
        "signal_count": sum(len(v) for v in signals.values()),
    }
