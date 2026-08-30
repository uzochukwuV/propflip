#!/usr/bin/env bash
set -u
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
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
