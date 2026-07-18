#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
python3 "$ROOT/scripts/clean_legacy_calendar_snapshots.py" --root "$ROOT"
echo "Now run: python3 scripts/run_quality_gate.py --strict-native-lanes"
