# llm-local-investigator

Local Linux system freeze investigation workflow using LangGraph. Orchestrates a multi-step investigation: executes probe commands on a frozen Linux system, analyzes output with a local LLM (llama.cpp), and presents findings via a Flask dashboard.

## Stack

Python 3, LangGraph, Flask, llama.cpp, SQLite

## Structure

```
llm-local-investigator/
├── app/           # Main package (18 modules)
│   ├── graph/     # LangGraph workflow
│   ├── probes/    # System command execution
│   ├── analysis/  # LLM-powered analysis
│   └── dashboard/ # Flask web UI
├── data/          # SQLite storage
├── reports/       # Generated findings
└── requirements.txt
```

## Usage

```bash
pip install -r requirements.txt
python -m app.cli
```

Or with the web dashboard:
```bash
python -m app.dashboard
```

## License

MIT
