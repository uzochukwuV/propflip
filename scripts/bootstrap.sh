#!/usr/bin/env bash
# Idempotent env bootstrap. This sandbox wipes ~/.local/bin/uv and .venv between
# turns, so every run must self-recover. We install uv into the project tree
# (.uv-bin) so the binary itself persists alongside source.
set -u
PROJ=/workspace/86f7610d-18e7-4a1b-ba50-ff3b60d660c4/sessions/agent_ef2d0c4e-6c72-4250-9050-527e0796e94d
cd "$PROJ"
mkdir -p logs .uv-bin
UV="$PROJ/.uv-bin/uv"
if ! "$UV" version >/dev/null 2>&1; then
  echo "bootstrapping uv..." >&2
  UV_INSTALL_DIR="$PROJ/.uv-bin" sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' >>logs/uv_install.log 2>&1
fi
"$UV" venv .venv --python 3.10 >>logs/venv.log 2>&1 || true
"$UV" sync >>logs/sync.log 2>&1
echo "ready: $("$UV" --version 2>&1)"
