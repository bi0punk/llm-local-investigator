from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from langgraph.graph import END, START, StateGraph
except Exception:
    from .compat_graph import END, START, StateGraph

from .config import SETTINGS
from .llm_client import LLMClient
from .probes import base_artifacts, decide_extra_profiles, extra_artifacts, load_snapshots_around
from .reporting import render_html, render_markdown
from .rules import evaluate_rules
from .state import IncidentState
from .storage import Storage
from .trace import run_traced_node
from .utils import ensure_dir, shorten, write_json, write_text


def _make_llm_evidence(state: IncidentState, include_extra: bool = False) -> Dict[str, Any]:
    artifacts = dict(state.get("artifacts", {}))
    if include_extra:
        artifacts.update(state.get("extra_artifacts", {}))
    payload = {
        "incident_ts": state["incident_ts"],
        "rule_summary": state.get("rule_summary", {}),
        "snapshots": state.get("snapshots", {}),
        "artifacts": {k: shorten(v, SETTINGS.max_log_chars) for k, v in artifacts.items()},
    }
    return payload


def _persist_llm_trace_files(outdir: Path, llm_trace: Dict[str, Any]) -> Dict[str, Any]:
    llm_dir = ensure_dir(outdir / "llm")
    pass_name = llm_trace.get("pass_name", "unknown")
    request_path = llm_dir / f"{pass_name}.request.json"
    raw_response_path = llm_dir / f"{pass_name}.response.raw.txt"
    parsed_path = llm_dir / f"{pass_name}.parsed.json"

    write_json(request_path, llm_trace.get("request_payload", {}))
    write_text(raw_response_path, llm_trace.get("response_text", ""))
    write_json(parsed_path, llm_trace.get("parsed_json", {}))

    enriched = dict(llm_trace)
    enriched["request_path"] = str(request_path)
    enriched["raw_response_path"] = str(raw_response_path)
    enriched["parsed_path"] = str(parsed_path)
    return enriched


def node_collect(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        outdir = ensure_dir(current["outdir"])
        artifacts = base_artifacts(
            since=current["since"],
            until=current["until"],
            include_previous_boot=SETTINGS.include_previous_boot,
        )
        snapshots = load_snapshots_around(
            snapshot_dir=SETTINGS.snapshot_dir,
            incident_ts=current["incident_ts"],
            minutes=SETTINGS.extra_snapshot_window_min,
            max_rows=SETTINGS.max_snapshot_rows,
        )
        write_json(outdir / "artifacts.base.json", artifacts)
        write_json(outdir / "snapshots.window.json", snapshots)
        return {
            "artifacts": artifacts,
            "snapshots": snapshots,
            "_trace_note": f"collected {len(artifacts)} base artifacts and {len(snapshots.get('rows', []))} snapshots",
        }

    return run_traced_node(state, "collect", worker)


def node_rules(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        summary = evaluate_rules(current.get("artifacts", {}), max_lines=SETTINGS.max_signal_lines)
        return {
            "signals": summary["signals"],
            "rule_summary": summary,
            "_trace_note": f"detected {summary.get('signal_count', 0)} signal lines; strongest={summary.get('strongest_signal', 'unknown')}",
        }

    return run_traced_node(state, "rules", worker)


def node_preliminary_llm(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        calls = list(current.get("llm_calls", []))
        if current.get("skip_llm"):
            analysis = {
                "summary": "LLM step skipped by user; report is based on rule engine and collected artifacts.",
                "overall_confidence": 0.25,
                "analysis_notes": ["LLM disabled via --skip-llm"],
                "evidence_map": [],
                "top_hypotheses": [],
                "missing_evidence": ["LLM disabled via --skip-llm"],
                "recommended_priority": "medium",
            }
            calls.append(
                {
                    "pass_name": "preliminary",
                    "status": "skipped",
                    "created_at": "",
                    "request_preview": "",
                    "response_preview": "",
                    "response_text": "",
                    "parsed_json": analysis,
                    "usage": {},
                }
            )
            return {
                "preliminary_analysis": analysis,
                "llm_calls": calls,
                "_trace_note": "preliminary llm skipped",
            }

        client = LLMClient()
        result = client.analyze(current["incident_ts"], _make_llm_evidence(current, include_extra=False), pass_name="preliminary")
        enriched_trace = _persist_llm_trace_files(Path(current["outdir"]), result["trace"])
        calls.append(enriched_trace)
        return {
            "preliminary_analysis": result["analysis"],
            "llm_calls": calls,
            "_trace_note": f"preliminary llm status={enriched_trace.get('status')}",
        }

    return run_traced_node(state, "preliminary_llm", worker)


def node_decide_extra(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        rule_summary = current.get("rule_summary", {})
        prelim = current.get("preliminary_analysis", {})
        profiles = decide_extra_profiles(current.get("signals", {}))
        missing = prelim.get("missing_evidence", []) if isinstance(prelim, dict) else []
        overall_conf = float(prelim.get("overall_confidence", 0.0)) if isinstance(prelim, dict) else 0.0

        reason_parts = []
        run_extra = False
        if not rule_summary.get("has_high_signal"):
            run_extra = True
            reason_parts.append("rule engine did not find a strong signal")
        if overall_conf < 0.70:
            run_extra = True
            reason_parts.append(f"preliminary LLM confidence is low ({overall_conf})")
        if missing:
            run_extra = True
            reason_parts.append("LLM requested more evidence")
        if profiles:
            reason_parts.append("profiles inferred from signals: " + ", ".join(profiles))

        return {
            "decision": {
                "run_extra_probes": run_extra,
                "profiles": profiles,
                "reason": "; ".join(reason_parts) if reason_parts else "No extra probes needed",
            },
            "_trace_note": f"run_extra={run_extra}; profiles={','.join(profiles) if profiles else 'none'}",
        }

    return run_traced_node(state, "decide_extra", worker)


def route_after_decision(state: IncidentState) -> str:
    decision = state.get("decision", {})
    if decision.get("run_extra_probes"):
        return "extra_probes"
    return "finalize_without_extra"


def node_extra_probes(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        outdir = ensure_dir(current["outdir"])
        profiles = current.get("decision", {}).get("profiles", [])
        artifacts = extra_artifacts(profiles)
        write_json(outdir / "artifacts.extra.json", artifacts)
        return {
            "extra_artifacts": artifacts,
            "_trace_note": f"extra probes collected for profiles: {', '.join(profiles) if profiles else 'none'}",
        }

    return run_traced_node(state, "extra_probes", worker)


def node_final_llm(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        if current.get("skip_llm"):
            return {
                "final_analysis": current.get("preliminary_analysis", {}),
                "_trace_note": "final llm skipped because skip_llm is true",
            }
        client = LLMClient()
        result = client.analyze(current["incident_ts"], _make_llm_evidence(current, include_extra=True), pass_name="final")
        calls = list(current.get("llm_calls", []))
        enriched_trace = _persist_llm_trace_files(Path(current["outdir"]), result["trace"])
        calls.append(enriched_trace)
        return {
            "final_analysis": result["analysis"],
            "llm_calls": calls,
            "_trace_note": f"final llm status={enriched_trace.get('status')}",
        }

    return run_traced_node(state, "final_llm", worker)


def node_finalize_without_extra(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        return {
            "final_analysis": current.get("preliminary_analysis", {}),
            "_trace_note": "reused preliminary analysis without extra probes",
        }

    return run_traced_node(state, "finalize_without_extra", worker)


def node_report(state: IncidentState) -> IncidentState:
    def worker(current: IncidentState) -> IncidentState:
        outdir = ensure_dir(current["outdir"])
        md = render_markdown(current)
        html = render_html(current)
        write_text(outdir / "report.md", md)
        write_text(outdir / "report.html", html)
        write_json(outdir / "trace.events.json", current.get("trace_events", []))
        write_json(outdir / "llm.calls.json", current.get("llm_calls", []))
        write_json(
            outdir / "state.summary.json",
            {
                "incident_ts": current.get("incident_ts"),
                "since": current.get("since"),
                "until": current.get("until"),
                "outdir": current.get("outdir"),
                "rule_summary": current.get("rule_summary", {}),
                "decision": current.get("decision", {}),
                "preliminary_analysis": current.get("preliminary_analysis", {}),
                "final_analysis": current.get("final_analysis", {}),
                "metadata": current.get("metadata", {}),
            },
        )
        return {
            "report_md": md,
            "report_html": html,
            "_trace_note": "report files and trace files written",
        }

    return run_traced_node(state, "report", worker)


def node_persist(state: IncidentState) -> IncidentState:
    # Persist is handled manually so the final trace file also contains the persist step.
    from time import perf_counter
    from .utils import now_iso

    started_at = now_iso()
    t0 = perf_counter()
    try:
        storage = Storage()
        incident_id = storage.upsert_incident_from_state(state)
        status = "ok"
        note = f"incident persisted to sqlite with id={incident_id}"
        partial = {"db_incident_id": incident_id}
    except Exception as exc:
        status = "error"
        note = str(exc)
        partial = {"errors": list(state.get("errors", [])) + [f"persist: {exc}"]}

    finished_at = now_iso()
    entry = {
        "node_name": "persist",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((perf_counter() - t0) * 1000),
        "note": note,
    }
    traces = list(state.get("trace_events", [])) + [entry]
    partial["trace_events"] = traces

    outdir = ensure_dir(state["outdir"])
    write_json(outdir / "trace.events.json", traces)
    write_json(outdir / "llm.calls.json", state.get("llm_calls", []))
    if status == "ok":
        # Re-run upsert so trace records in SQLite include the persist node too.
        storage = Storage()
        incident_id = storage.upsert_incident_from_state({**state, **partial})
        partial["db_incident_id"] = incident_id

    return partial


def build_graph():
    graph = StateGraph(IncidentState)
    graph.add_node("collect", node_collect)
    graph.add_node("rules", node_rules)
    graph.add_node("preliminary_llm", node_preliminary_llm)
    graph.add_node("decide_extra", node_decide_extra)
    graph.add_node("extra_probes", node_extra_probes)
    graph.add_node("final_llm", node_final_llm)
    graph.add_node("finalize_without_extra", node_finalize_without_extra)
    graph.add_node("report", node_report)
    graph.add_node("persist", node_persist)

    graph.add_edge(START, "collect")
    graph.add_edge("collect", "rules")
    graph.add_edge("rules", "preliminary_llm")
    graph.add_edge("preliminary_llm", "decide_extra")
    graph.add_conditional_edges(
        "decide_extra",
        route_after_decision,
        {
            "extra_probes": "extra_probes",
            "finalize_without_extra": "finalize_without_extra",
        },
    )
    graph.add_edge("extra_probes", "final_llm")
    graph.add_edge("final_llm", "report")
    graph.add_edge("finalize_without_extra", "report")
    graph.add_edge("report", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
