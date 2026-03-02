PYTHON ?= python3

venv:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

healthcheck:
	$(PYTHON) run.py healthcheck --allow-offline

investigate:
	$(PYTHON) run.py investigate --incident "2026-02-28 07:00:00"

dashboard:
	$(PYTHON) run.py serve-dashboard

snapshot:
	$(PYTHON) run.py snapshot-once
