#!/usr/bin/env bash
set -e
printf '%s\n' 'scripts/global_metrics.py is deprecated in aictx v3. Global metrics aggregation was removed; use `aictx report real-usage --repo <repo>` instead.' >&2
exit 2
