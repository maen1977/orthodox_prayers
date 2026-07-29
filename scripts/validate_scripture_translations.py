#!/usr/bin/env python3
"""Compatibility entry point: translations are forbidden; validate native lanes."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
path = sys.argv[1] if len(sys.argv) > 1 else "data/calendar/today.json"
subprocess.run([sys.executable, "scripts/validate_daily_native_content.py", path], cwd=ROOT, check=True)
print("Scripture policy validated: no cross-language translation; only exact same-language official text may be non-empty")
