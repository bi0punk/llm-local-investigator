from __future__ import annotations

import time
from pathlib import Path

from .config import SETTINGS
from .probes import capture_snapshot_once
from .storage import Storage


def snapshot_once(snapshot_dir: str | Path | None = None) -> dict:
    snapshot_dir = Path(snapshot_dir or SETTINGS.snapshot_dir)
    data = capture_snapshot_once(snapshot_dir=snapshot_dir)
    Storage().record_snapshot(data)
    return data


def snapshot_loop(interval_sec: int = 60, snapshot_dir: str | Path | None = None) -> None:
    snapshot_dir = Path(snapshot_dir or SETTINGS.snapshot_dir)
    while True:
        data = snapshot_once(snapshot_dir=snapshot_dir)
        print(f"[snapshot] captured_at={data.get('captured_at')} source_file={data.get('source_file')}")
        time.sleep(interval_sec)
