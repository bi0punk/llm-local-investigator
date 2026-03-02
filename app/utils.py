from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def ensure_dir(path: os.PathLike[str] | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: os.PathLike[str] | str, data: Any) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: os.PathLike[str] | str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def read_json_if_exists(path: os.PathLike[str] | str) -> Optional[Any]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_text_if_exists(path: os.PathLike[str] | str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def ts_folder_name(ts_str: str) -> str:
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("incident_%Y%m%d_%H%M%S")


def compute_window(incident_ts: str, before_min: int, after_min: int) -> tuple[str, str]:
    dt = datetime.strptime(incident_ts, "%Y-%m-%d %H:%M:%S")
    since = (dt - timedelta(minutes=before_min)).strftime("%Y-%m-%d %H:%M:%S")
    until = (dt + timedelta(minutes=after_min)).strftime("%Y-%m-%d %H:%M:%S")
    return since, until


def shorten(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n...[TRUNCATED]...\n\n" + text[-half:]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    for candidate in _candidate_json_strings(text):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _candidate_json_strings(text: str) -> Iterable[str]:
    code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for block in code_blocks:
        yield block

    stack = 0
    start = None
    for idx, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = idx
            stack += 1
        elif ch == "}":
            if start is not None:
                stack -= 1
                if stack == 0:
                    yield text[start : idx + 1]
                    start = None


def json_preview(data: Any, max_chars: int = 4000) -> str:
    try:
        raw = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        raw = str(data)
    return shorten(raw, max_chars)
