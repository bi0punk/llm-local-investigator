from __future__ import annotations

import time
from typing import Any, Callable, Dict

from .utils import now_iso


def run_traced_node(state: Dict[str, Any], node_name: str, worker: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
    started_at = now_iso()
    t0 = time.perf_counter()
    try:
        partial = worker(state) or {}
        status = "ok"
        note = partial.pop("_trace_note", "")
    except Exception as exc:
        partial = {
            "errors": list(state.get("errors", [])) + [f"{node_name}: {exc}"],
            "_trace_note": str(exc),
        }
        status = "error"
        note = str(exc)

    finished_at = now_iso()
    duration_ms = int((time.perf_counter() - t0) * 1000)

    if not note:
        visible_keys = [k for k in partial.keys() if not k.startswith("_")]
        note = "updated keys: " + ", ".join(visible_keys) if visible_keys else "no visible updates"

    entry = {
        "node_name": node_name,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "note": note,
    }

    partial["trace_events"] = list(state.get("trace_events", [])) + [entry]
    return partial
