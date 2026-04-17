#!/usr/bin/env bash
set -e
if command -v aictx >/dev/null 2>&1; then
  exec aictx task-memory "$@"
fi
PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PWD/src" exec python3 -m aictx task-memory "$@"
