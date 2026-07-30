#!/usr/bin/env python3
"""Apply the R20 quality-gate hotfix after extracting this patch at repository root."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / "data" / "rolling-week" / "candidates" / "2026-07-28"

if LEGACY.exists():
    shutil.rmtree(LEGACY)
    print(f"REMOVED_LEGACY_UNSIGNED_CANDIDATE path={LEGACY.relative_to(ROOT)}")
else:
    print(f"LEGACY_UNSIGNED_CANDIDATE_ABSENT path={LEGACY.relative_to(ROOT)}")

parent = LEGACY.parent
while parent != ROOT and parent.exists() and not any(parent.iterdir()):
    parent.rmdir()
    parent = parent.parent

print("R20_QUALITY_GATE_HOTFIX_APPLIED")
