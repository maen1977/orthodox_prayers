#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python scripts/verify_r11_patch.py
python -m unittest discover -s tests -p 'test_*.py'
echo 'R11_APPLY_OK: files are in the repository root.'
