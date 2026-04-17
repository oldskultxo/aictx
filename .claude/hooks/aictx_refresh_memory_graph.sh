#!/bin/sh
set -eu
REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
aictx memory-graph --refresh >/dev/null 2>&1 || true
aictx global --refresh >/dev/null 2>&1 || true
exit 0
