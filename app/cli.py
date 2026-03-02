from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import SETTINGS
from .dashboard import create_app
from .graph_flow import build_graph
from .llm_client import LLMClient
from .snapshot import snapshot_loop, snapshot_once
from .storage import Storage
from .utils import compute_window, ensure_dir, ts_folder_name


def _cmd_investigate(args: argparse.Namespace) -> int:
    since, until = compute_window(args.incident, args.window_before, args.window_after)
    outdir = ensure_dir(Path(args.output_dir) / ts_folder_name(args.incident))

    graph = build_graph()
    result = graph.invoke(
        {
            "incident_ts": args.incident,
            "since": since,
            "until": until,
            "outdir": str(outdir),
            "skip_llm": args.skip_llm,
            "trace_events": [],
            "llm_calls": [],
            "metadata": {"requested_by_cli": True, "version": "0.2.0"},
        }
    )

    print(result.get("report_md", ""))
    if args.print_trace:
        print("\n=== TRACE EVENTS ===")
        print(json.dumps(result.get("trace_events", []), indent=2, ensure_ascii=False))
        print("\n=== LLM CALLS ===")
        print(json.dumps(result.get("llm_calls", []), indent=2, ensure_ascii=False))
    print(f"\nArtifacts written to: {outdir}")
    print(f"SQLite incident id: {result.get('db_incident_id')}")
    return 0


def _cmd_snapshot_once(args: argparse.Namespace) -> int:
    data = snapshot_once(snapshot_dir=args.snapshot_dir)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def _cmd_snapshot_loop(args: argparse.Namespace) -> int:
    snapshot_loop(interval_sec=args.interval, snapshot_dir=args.snapshot_dir)
    return 0


def _cmd_healthcheck(args: argparse.Namespace) -> int:
    client = LLMClient()
    info = client.healthcheck()
    payload = {
        "llm": info,
        "output_dir": str(SETTINGS.output_dir),
        "snapshot_dir": str(SETTINGS.snapshot_dir),
        "database_path": str(SETTINGS.database_path),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if info.get("reachable") or args.allow_offline else 2


def _cmd_dashboard(args: argparse.Namespace) -> int:
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)
    return 0


def _cmd_reindex(args: argparse.Namespace) -> int:
    storage = Storage()
    incidents = storage.reindex_outputs(args.output_dir)
    snapshots = storage.reindex_snapshots(args.snapshot_dir)
    print(json.dumps({"reindexed_incidents": incidents, "reindexed_snapshots": snapshots}, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local freeze investigator with LangGraph + llama.cpp + SQLite dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("investigate", help="Analyze a freeze/hang incident around a timestamp")
    p_inv.add_argument("--incident", required=True, help="YYYY-mm-dd HH:MM:SS")
    p_inv.add_argument("--window-before", type=int, default=SETTINGS.default_window_before_min)
    p_inv.add_argument("--window-after", type=int, default=SETTINGS.default_window_after_min)
    p_inv.add_argument("--output-dir", default=str(SETTINGS.output_dir))
    p_inv.add_argument("--skip-llm", action="store_true", help="Generate rule-based report without calling llama.cpp")
    p_inv.add_argument("--print-trace", action="store_true", help="Print node traces and LLM call traces to stdout")
    p_inv.set_defaults(func=_cmd_investigate)

    p_snap = sub.add_parser("snapshot-once", help="Capture a single preventive snapshot")
    p_snap.add_argument("--snapshot-dir", default=str(SETTINGS.snapshot_dir))
    p_snap.set_defaults(func=_cmd_snapshot_once)

    p_loop = sub.add_parser("snapshot-loop", help="Capture snapshots continuously")
    p_loop.add_argument("--interval", type=int, default=60)
    p_loop.add_argument("--snapshot-dir", default=str(SETTINGS.snapshot_dir))
    p_loop.set_defaults(func=_cmd_snapshot_loop)

    p_health = sub.add_parser("healthcheck", help="Check local llama.cpp server connectivity")
    p_health.add_argument("--allow-offline", action="store_true")
    p_health.set_defaults(func=_cmd_healthcheck)

    p_dash = sub.add_parser("serve-dashboard", help="Run the local dashboard")
    p_dash.add_argument("--host", default=SETTINGS.dashboard_host)
    p_dash.add_argument("--port", type=int, default=SETTINGS.dashboard_port)
    p_dash.set_defaults(func=_cmd_dashboard)

    p_reindex = sub.add_parser("reindex", help="Reindex outputs and snapshots into SQLite")
    p_reindex.add_argument("--output-dir", default=str(SETTINGS.output_dir))
    p_reindex.add_argument("--snapshot-dir", default=str(SETTINGS.snapshot_dir))
    p_reindex.set_defaults(func=_cmd_reindex)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
