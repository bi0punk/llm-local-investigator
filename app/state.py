from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class IncidentState(TypedDict, total=False):
    incident_ts: str
    since: str
    until: str
    outdir: str
    skip_llm: bool
    artifacts: Dict[str, str]
    extra_artifacts: Dict[str, str]
    snapshots: Dict[str, Any]
    signals: Dict[str, List[str]]
    rule_summary: Dict[str, Any]
    preliminary_analysis: Dict[str, Any]
    final_analysis: Dict[str, Any]
    decision: Dict[str, Any]
    llm_calls: List[Dict[str, Any]]
    trace_events: List[Dict[str, Any]]
    report_md: str
    report_html: str
    errors: List[str]
    metadata: Dict[str, Any]
    db_incident_id: int
