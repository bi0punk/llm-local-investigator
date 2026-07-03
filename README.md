# llm-local-investigator

[![CI](https://github.com/bi0punk/llm-local-investigator/actions/workflows/ci.yml/badge.svg)](https://github.com/bi0punk/llm-local-investigator/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Local Linux system freeze investigation workflow using LangGraph. Orchestrates a multi-step investigation: executes probe commands on a frozen Linux system, analyzes output with a local LLM (llama.cpp), and presents findings via a Flask dashboard.

## Tabla de contenidos

- [Características](#características)
- [Stack](#stack)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Tests](#tests)
- [CI](#ci)
- [Configuración](#configuración)
- [Datos](#datos)
- [Limitaciones y roadmap](#limitaciones-y-roadmap)
- [Licencia](#licencia)

## Características

- Workflow LangGraph: captura de artefactos → análisis basado en reglas → análisis LLM (preliminar + final) → reporte.
- Probes de sistema (dmesg/journalctl/sensors/top/ps/etc.) con detección de perfiles extra (disk, memory, net).
- Análisis con reglas (oom-killer, lockups, etc.) + LLM local (llama.cpp, OpenAI-compatible).
- Persistencia en SQLite (incidentes, traces, LLM calls, snapshots).
- Dashboard Flask para revisar incidentes históricos.
- Snapshots preventivos cada minuto vía systemd timer.
- Reportes HTML + Markdown por incidente.

## Stack

- **Lenguaje**: Python 3.12+
- **Workflow**: LangGraph (con fallback `compat_graph` si langgraph no está).
- **Web**: Flask (dashboard).
- **LLM**: llama.cpp (servidor OpenAI-compatible local).
- **DB**: SQLite.
- **Validación**: Pydantic.
- **Calidad**: ruff (lint), pytest.

## Arquitectura

```
 incident timestamp
        │
        ▼
┌────────────────┐    ┌─────────────────┐
│  app.probes     │ ─► │  app.rules       │  (regex: oom, lockup, ...)
│  (dmesg, journal,│    │  → signals +     │
│   sensors, ps…)  │    │  rule_summary    │
└────────────────┘    └────────┬─────────┘
                               │
        ┌──────────────────────┘
        ▼
┌────────────────┐    ┌─────────────────┐
│ app.llm_client  │ ─► │  app.reporting   │
│ (llama.cpp /v1/ │    │  → report.md/html│
│  chat)          │    │  + persist trace │
└────────────────┘    └────────┬─────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │  app.storage     │  SQLite
                     │  (incidents,     │
                     │   traces, llm)   │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  app.dashboard   │  Flask
                     └─────────────────┘
```

- **app/graph_flow.py**: define el grafo LangGraph (nodos: probe → rule → llm_preliminary → llm_final → persist → report).
- **app/compat_graph.py**: implementación mínima de StateGraph si langgraph no está disponible.
- **app/cli.py**: CLI con subcomandos.
- **app/storage.py**: capa SQLite.
- **app/snapshot.py**: snapshots preventivos continuos.

## Requisitos

- Linux nativo (usa comandos del sistema: `dmesg`, `journalctl`, `sensors`, `ps`, `top`).
- Python 3.12+.
- llama.cpp server (opcional si `--skip-llm` o `FI_ALLOW_OFFLINE=1`).
- Comandos opcionales: `sensors` (lm-sensors), `smartctl`, `ip`.

## Instalación

```bash
uv venv -p 3.12 .venv
uv pip install -e ".[dev]"
# o con pip:
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Servicios systemd (snapshots cada minuto + dashboard):

```bash
sudo ./scripts/install_ubuntu.sh
sudo systemctl enable --now freeze-snapshot.timer freeze-dashboard.service
```

## Uso

CLI (`run.py` o `python -m app.cli`):

```bash
# Investigar un incidente alrededor de un timestamp:
python run.py investigate --incident "2026-02-28 07:00:00"

# Snapshot preventivo único:
python run.py snapshot-once

# Loop continuo de snapshots (o usa el systemd timer):
python run.py snapshot-loop

# Healthcheck del servidor LLM local:
python run.py healthcheck

# Dashboard web:
python run.py serve-dashboard

# Reindexar outputs/ y snapshots/ en SQLite:
python run.py reindex
```

Atajos en el `Makefile`: `make investigate`, `make snapshot`, `make dashboard`, `make healthcheck`.

## Tests

```bash
pytest -q
```

Smoke tests (`tests/test_smoke.py`): imports de módulos de `app`, subcomandos del CLI, higiene del repo (sin DB/outputs/snapshots commiteados), deps listadas. No requieren llama.cpp real.

## CI

GitHub Actions (`.github/workflows/ci.yml`) sobre Python 3.12:

- **lint** — `ruff check .`
- **test** — `pip install -e ".[dev]"` + `pytest -q`

## Configuración

Variables de entorno (ver `app/config.py`, prefijo `FI_`):

- `FI_LLM_BASE_URL` — URL del servidor llama.cpp (default `http://127.0.0.1:8080`).
- `FI_LLM_MODEL` — nombre del modelo (default `local-model`).
- `FI_LLM_TIMEOUT`, `FI_LLM_TEMPERATURE`, `FI_LLM_MAX_TOKENS` — params LLM.
- `FI_ALLOW_OFFLINE` — si `1`, permite correr sin LLM (modo fallback).
- Rutas de `db/`, `outputs/`, `snapshots/` configurables.

## Datos

Directorios runtime (todos gitignored, se regeneran):

- `db/freeze_investigator.sqlite3` — almacenamiento principal.
- `outputs/incident_<timestamp>/` — reportes (`.md`/`.html`), traces, LLM calls, artefactos por incidente.
- `snapshots/YYYYMMDD.jsonl` — snapshots preventivos (uno por minuto).

## Limitaciones y roadmap

- **Limitación**: requiere comandos Linux y permisos (dmesg/journalctl pueden necesitar `sudo`/grupo `systemd-journal`).
- **Limitación**: sin tests del workflow end-to-end (necesita LLM real + sistema con incidentes).
- **Roadmap**: más probes (perf, eBPF), correlación multi-incidente, alertas proactivas.

## Licencia

MIT — ver [LICENSE](LICENSE).
