#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python run.py investigate --incident "2026-02-28 07:00:00"
