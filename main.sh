#!/bin/bash -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/.venv/bin/python" "$DIR/main.py" "$@"
