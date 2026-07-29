#!/usr/bin/env python3
"""Deprecated name; forwards to the independent native-language coverage audit."""
from __future__ import annotations

import runpy
from pathlib import Path

print("NOTE: use scripts/check_native_coverage.py; no translation is performed.")
runpy.run_path(str(Path(__file__).with_name("check_native_coverage.py")), run_name="__main__")
