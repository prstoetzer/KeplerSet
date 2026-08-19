#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script must run on macOS." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This build is intentionally native Apple Silicon ARM64; current architecture is $(uname -m)." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . -r requirements-build.txt
python scripts/build.py

echo
echo "Built:"
echo "  dist/KeplerSet.app"
echo "  dist/KeplerSetCLI"
