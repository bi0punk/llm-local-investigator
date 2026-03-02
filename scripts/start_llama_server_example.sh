#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-/models/model.gguf}"
PORT="${2:-8080}"

./llama-server -m "$MODEL_PATH" --port "$PORT"
