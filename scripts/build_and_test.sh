#!/usr/bin/env bash
set -u
LOG=/tmp/agent_ef2d0c4e-6c72-4250-9050-527e0796e94d/studio_build.log
: > "$LOG"
cd /workspace/86f7610d-18e7-4a1b-ba50-ff3b60d660c4/sessions/agent_ef2d0c4e-6c72-4250-9050-527e0796e94d
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
