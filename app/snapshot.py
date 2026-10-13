from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

from .config import SETTINGS
from .probes import capture_snapshot_once
from .storage import Storage

_running = True


def _handle_signal(signum, _frame):
    global _running
    print(f"[snapshot] señal {signum} recibida, cerrando...", file=sys.stderr)
    _running = False


def snapshot_once(snapshot_dir: str | Path | None = None) -> dict:
    snapshot_dir = Path(snapshot_dir or SETTINGS.snapshot_dir)
    data = capture_snapshot_once(snapshot_dir=snapshot_dir)
    Storage().record_snapshot(data)
    return data


def snapshot_loop(interval_sec: int = 60, snapshot_dir: str | Path | None = None) -> None:
    global _running
    snapshot_dir = Path(snapshot_dir or SETTINGS.snapshot_dir)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while _running:
        try:
            data = snapshot_once(snapshot_dir=snapshot_dir)
            print(f"[snapshot] captured_at={data.get('captured_at')} source_file={data.get('source_file')}")
        except Exception as exc:
            print(f"[snapshot] ERROR: {exc}", file=sys.stderr)
        if _running:
            time.sleep(interval_sec)

    print("[snapshot] loop finalizado correctamente.", file=sys.stderr)
