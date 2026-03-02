from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SETTINGS
from .utils import ensure_dir, now_iso, read_json_if_exists, read_text_if_exists


class Storage:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or SETTINGS.database_path)
        ensure_dir(self.db_path.parent)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_ts TEXT NOT NULL,
                    since_ts TEXT NOT NULL,
                    until_ts TEXT NOT NULL,
                    outdir TEXT NOT NULL UNIQUE,
                    summary TEXT,
                    overall_confidence REAL,
                    recommended_priority TEXT,
                    top_category TEXT,
                    strongest_signal TEXT,
                    decision_reason TEXT,
                    created_at TEXT NOT NULL,
                    report_md_path TEXT,
                    report_html_path TEXT,
                    rule_summary_json TEXT,
                    final_analysis_json TEXT,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    node_name TEXT,
                    status TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    note TEXT,
                    payload_json TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS llm_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    pass_name TEXT,
                    status TEXT,
                    created_at TEXT,
                    request_preview TEXT,
                    response_preview TEXT,
                    usage_json TEXT,
                    parsed_json TEXT,
                    raw_response_path TEXT,
                    request_path TEXT,
                    parsed_path TEXT,
                    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    source_file TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(captured_at, source_file)
                );
                """
            )

    def upsert_incident_from_state(self, state: Dict[str, Any]) -> int:
        analysis = state.get("final_analysis") or state.get("preliminary_analysis") or {}
        rule_summary = state.get("rule_summary", {})
        outdir = str(state["outdir"])
        report_md_path = str(Path(outdir) / "report.md")
        report_html_path = str(Path(outdir) / "report.html")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    incident_ts, since_ts, until_ts, outdir, summary, overall_confidence,
                    recommended_priority, top_category, strongest_signal, decision_reason,
                    created_at, report_md_path, report_html_path, rule_summary_json,
                    final_analysis_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(outdir) DO UPDATE SET
                    incident_ts=excluded.incident_ts,
                    since_ts=excluded.since_ts,
                    until_ts=excluded.until_ts,
                    summary=excluded.summary,
                    overall_confidence=excluded.overall_confidence,
                    recommended_priority=excluded.recommended_priority,
                    top_category=excluded.top_category,
                    strongest_signal=excluded.strongest_signal,
                    decision_reason=excluded.decision_reason,
                    report_md_path=excluded.report_md_path,
                    report_html_path=excluded.report_html_path,
                    rule_summary_json=excluded.rule_summary_json,
                    final_analysis_json=excluded.final_analysis_json,
                    metadata_json=excluded.metadata_json
                """,
                (
                    state.get("incident_ts"),
                    state.get("since"),
                    state.get("until"),
                    outdir,
                    analysis.get("summary", ""),
                    float(analysis.get("overall_confidence", 0.0) or 0.0),
                    analysis.get("recommended_priority", "medium"),
                    (analysis.get("top_hypotheses", [{}]) or [{}])[0].get("category", "unknown"),
                    rule_summary.get("strongest_signal", "unknown"),
                    state.get("decision", {}).get("reason", ""),
                    now_iso(),
                    report_md_path,
                    report_html_path,
                    json.dumps(rule_summary, ensure_ascii=False),
                    json.dumps(analysis, ensure_ascii=False),
                    json.dumps(state.get("metadata", {}), ensure_ascii=False),
                ),
            )
            incident_id = conn.execute("SELECT id FROM incidents WHERE outdir = ?", (outdir,)).fetchone()["id"]

            conn.execute("DELETE FROM traces WHERE incident_id = ?", (incident_id,))
            conn.execute("DELETE FROM llm_calls WHERE incident_id = ?", (incident_id,))

            for item in state.get("trace_events", []):
                conn.execute(
                    """
                    INSERT INTO traces (
                        incident_id, node_name, status, started_at, finished_at, duration_ms, note, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        item.get("node_name"),
                        item.get("status"),
                        item.get("started_at"),
                        item.get("finished_at"),
                        item.get("duration_ms"),
                        item.get("note"),
                        json.dumps(item, ensure_ascii=False),
                    ),
                )

            for item in state.get("llm_calls", []):
                conn.execute(
                    """
                    INSERT INTO llm_calls (
                        incident_id, pass_name, status, created_at, request_preview, response_preview,
                        usage_json, parsed_json, raw_response_path, request_path, parsed_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        incident_id,
                        item.get("pass_name"),
                        item.get("status"),
                        item.get("created_at"),
                        item.get("request_preview", ""),
                        item.get("response_preview", ""),
                        json.dumps(item.get("usage", {}), ensure_ascii=False),
                        json.dumps(item.get("parsed_json", {}), ensure_ascii=False),
                        item.get("raw_response_path", ""),
                        item.get("request_path", ""),
                        item.get("parsed_path", ""),
                    ),
                )

        return int(incident_id)

    def record_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO snapshots (captured_at, source_file, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.get("captured_at"),
                    snapshot.get("source_file", ""),
                    json.dumps(snapshot, ensure_ascii=False),
                    now_iso(),
                ),
            )

    def list_incidents(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, incident_ts, since_ts, until_ts, outdir, summary, overall_confidence,
                       recommended_priority, top_category, strongest_signal, decision_reason, created_at
                FROM incidents
                ORDER BY incident_ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_incident(self, incident_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        for key in ("rule_summary_json", "final_analysis_json", "metadata_json"):
            try:
                data[key.replace("_json", "")] = json.loads(data.get(key) or "{}")
            except Exception:
                data[key.replace("_json", "")] = {}
        data["report_md"] = read_text_if_exists(data.get("report_md_path", ""))
        data["report_html"] = read_text_if_exists(data.get("report_html_path", ""))
        data["traces"] = self.list_traces(incident_id)
        data["llm_calls"] = self.list_llm_calls(incident_id)
        return data

    def list_traces(self, incident_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT node_name, status, started_at, finished_at, duration_ms, note
                FROM traces
                WHERE incident_id = ?
                ORDER BY id ASC
                """,
                (incident_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_llm_calls(self, incident_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pass_name, status, created_at, request_preview, response_preview,
                       usage_json, parsed_json, raw_response_path, request_path, parsed_path
                FROM llm_calls
                WHERE incident_id = ?
                ORDER BY id ASC
                """,
                (incident_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["usage"] = json.loads(item.get("usage_json") or "{}")
            except Exception:
                item["usage"] = {}
            try:
                item["parsed_json"] = json.loads(item.get("parsed_json") or "{}")
            except Exception:
                item["parsed_json"] = {}
            result.append(item)
        return result

    def list_snapshots(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, captured_at, source_file, payload_json
                FROM snapshots
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except Exception:
                item["payload"] = {}
            out.append(item)
        return out

    def reindex_outputs(self, output_dir: Path | str | None = None) -> int:
        output_dir = Path(output_dir or SETTINGS.output_dir)
        count = 0
        if not output_dir.exists():
            return 0
        for folder in sorted(output_dir.glob("incident_*")):
            state_summary = read_json_if_exists(folder / "state.summary.json")
            if not isinstance(state_summary, dict):
                continue
            trace_events = read_json_if_exists(folder / "trace.events.json") or []
            llm_calls = read_json_if_exists(folder / "llm.calls.json") or []
            state_summary["outdir"] = str(folder)
            state_summary["trace_events"] = trace_events
            state_summary["llm_calls"] = llm_calls
            self.upsert_incident_from_state(state_summary)
            count += 1
        return count

    def reindex_snapshots(self, snapshot_dir: Path | str | None = None) -> int:
        snapshot_dir = Path(snapshot_dir or SETTINGS.snapshot_dir)
        count = 0
        if not snapshot_dir.exists():
            return 0
        for path in sorted(snapshot_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                data["source_file"] = str(path)
                self.record_snapshot(data)
                count += 1
        return count
