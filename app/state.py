from __future__ import annotations

from typing import Any, TypedDict


class IncidentState(TypedDict, total=False):
    incident_ts: str
    since: str
    until: str
    outdir: str
    skip_llm: bool
    artifacts: dict[str, str]
    extra_artifacts: dict[str, str]
    snapshots: dict[str, Any]
    signals: dict[str, list[str]]
    rule_summary: dict[str, Any]
    preliminary_analysis: dict[str, Any]
    final_analysis: dict[str, Any]
    decision: dict[str, Any]
    llm_calls: list[dict[str, Any]]
    trace_events: list[dict[str, Any]]
    report_md: str
    report_html: str
    errors: list[str]
    metadata: dict[str, Any]
    db_incident_id: int
