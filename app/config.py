from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("FI_LLM_BASE_URL", "http://127.0.0.1:8080")
    llm_model: str = os.getenv("FI_LLM_MODEL", "local-model")
    llm_api_key: str = os.getenv("FI_LLM_API_KEY", "not-needed")
    llm_timeout: int = _env_int("FI_LLM_TIMEOUT", 180)
    llm_temperature: float = _env_float("FI_LLM_TEMPERATURE", 0.0)
    llm_max_tokens: int = _env_int("FI_LLM_MAX_TOKENS", 2200)
    llm_trace_chars: int = _env_int("FI_LLM_TRACE_CHARS", 24000)

    output_dir: Path = Path(os.getenv("FI_OUTPUT_DIR", "./outputs"))
    snapshot_dir: Path = Path(os.getenv("FI_SNAPSHOT_DIR", "./snapshots"))
    database_path: Path = Path(os.getenv("FI_DATABASE_PATH", "./db/freeze_investigator.sqlite3"))

    default_window_before_min: int = _env_int("FI_DEFAULT_WINDOW_BEFORE_MIN", 30)
    default_window_after_min: int = _env_int("FI_DEFAULT_WINDOW_AFTER_MIN", 20)
    extra_snapshot_window_min: int = _env_int("FI_EXTRA_SNAPSHOT_WINDOW_MIN", 90)
    include_previous_boot: bool = _env_bool("FI_INCLUDE_PREVIOUS_BOOT", True)
    max_log_chars: int = _env_int("FI_MAX_LOG_CHARS", 18000)
    max_signal_lines: int = _env_int("FI_MAX_SIGNAL_LINES", 12)
    max_snapshot_rows: int = _env_int("FI_MAX_SNAPSHOT_ROWS", 80)

    dashboard_host: str = os.getenv("FI_DASHBOARD_HOST", "127.0.0.1")
    dashboard_port: int = _env_int("FI_DASHBOARD_PORT", 8787)


SETTINGS = Settings()
