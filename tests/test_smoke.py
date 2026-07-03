"""Smoke tests para llm-local-investigator.

Validan imports del paquete app y higiene del repo (sin ejecutar el workflow
ni requerir llama.cpp real).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_app_modules_import():
    import app.config  # noqa: F401
    import app.graph_flow  # noqa: F401
    import app.llm_client  # noqa: F401
    import app.models  # noqa: F401
    import app.probes  # noqa: F401
    import app.reporting  # noqa: F401
    import app.rules  # noqa: F401
    import app.storage  # noqa: F401
    import app.utils  # noqa: F401


def test_cli_has_subcommands():
    """El CLI debe exponer los subcomandos esperados."""
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    for sub in ("investigate", "snapshot-once", "serve-dashboard", "healthcheck", "reindex"):
        assert sub in result.stdout, f"subcomando {sub} no aparece en --help"


def test_no_runtime_artifacts_tracked():
    """DB sqlite, outputs/ y snapshots/ no deben commitearse (se regeneran)."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    bad = [
        line
        for line in tracked.splitlines()
        if line.endswith(".sqlite3")
        or line.startswith("outputs/incident_")
        or (line.startswith("snapshots/") and line.endswith(".jsonl"))
    ]
    assert not bad, f"Artefactos runtime commiteados: {bad}"


def test_deps_listed():
    req = (REPO_ROOT / "requirements.txt").read_text()
    for dep in ("langgraph", "flask", "pydantic"):
        assert dep in req, f"{dep} no está en requirements.txt"
