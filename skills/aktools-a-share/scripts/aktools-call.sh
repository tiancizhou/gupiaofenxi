#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ]; then
  echo "usage: aktools-call.sh <selector> [key=value ...]" >&2
  exit 2
fi
mcporter call "$@"
