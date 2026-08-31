#!/usr/bin/env bash
set -u
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$PROJ/logs/build_and_test.log"
: > "$LOG"
cd "$PROJ"
export PATH="$HOME/.local/bin:$PATH"
echo "=== install uv ===" | tee -a "$LOG"
sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' >> "$LOG" 2>&1
command -v uv >> "$LOG" 2>&1 || echo "uv not on PATH" | tee -a "$LOG"
echo "=== venv + sync ===" | tee -a "$LOG"
uv venv .venv --python 3.10 >> "$LOG" 2>&1
uv sync >> "$LOG" 2>&1
echo "=== pytest ===" | tee -a "$LOG"
uv run pytest -q >> "$LOG" 2>&1 && echo "PYTEST_OK" >> "$LOG" || echo "PYTEST_NONZERO" >> "$LOG"
echo "=== smoke import ===" | tee -a "$LOG"
uv run python -c "import app.main, app.agents; print('IMPORT_OK')" >> "$LOG" 2>&1 || echo "IMPORT_FAIL" >> "$LOG"
echo "=== DONE ===" | tee -a "$LOG"
