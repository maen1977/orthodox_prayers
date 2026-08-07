#!/usr/bin/env python3
"""Validate that GitHub Actions is optional and never supplies daily content."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {"church-prayers.yml"}
files = {path.name for pattern in ("*.yml", "*.yaml") for path in WORKFLOWS.glob(pattern)}
if files != EXPECTED:
    raise SystemExit(f"Expected workflows {sorted(EXPECTED)}, found {sorted(files)}")

build = (WORKFLOWS / "church-prayers.yml").read_text(encoding="utf-8")
for token in (
    "name: Build Church Prayers",
    "python scripts/run_local_daily_release_gate.py",
    "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease",
    "output/Church-Prayers.apk",
    "output/Church-Prayers.aab",
    "name: Church-Prayers",
):
    if token not in build:
        raise SystemExit(f"Build workflow is missing required token: {token}")
for forbidden in (
    "schedule:",
    "update_language_lane.py",
    "production-data-signing",
    "VERIFIED_DATA_BRANCH",
    "DATA_SIGNING_PRIVATE_KEY_B64",
    "name: Daily Update",
):
    if forbidden in build:
        raise SystemExit(f"Build workflow contains obsolete daily-publication dependency: {forbidden}")

print("WORKFLOWS_OK files=1 optional_build=church-prayers.yml daily_content=local_android_engine")
