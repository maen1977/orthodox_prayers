#!/usr/bin/env python3
"""Validate the two visible workflows: app build and daily data update."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {"church-prayers.yml", "update.yml"}
files = {path.name for pattern in ("*.yml", "*.yaml") for path in WORKFLOWS.glob(pattern)}
if files != EXPECTED:
    raise SystemExit(f"Expected workflows {sorted(EXPECTED)}, found {sorted(files)}")

build = (WORKFLOWS / "church-prayers.yml").read_text(encoding="utf-8")
for token in (
    "name: Build Church Prayers",
    "python scripts/simple_quality_gate.py",
    "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease",
    "output/Church-Prayers.apk",
    "output/Church-Prayers.aab",
    "name: Church-Prayers",
):
    if token not in build:
        raise SystemExit(f"Build workflow is missing required token: {token}")
for forbidden in ("schedule:", "update_language_lane.py", "android-emulator-runner", "matrix:"):
    if forbidden in build:
        raise SystemExit(f"Build workflow contains unrelated complexity: {forbidden}")

update = (WORKFLOWS / "update.yml").read_text(encoding="utf-8")
for token in (
    "name: Daily Update",
    "schedule:",
    "options: [update, verify]",
    "name: Update Arabic lane",
    "name: Update Greek lane",
    "name: Update English lane",
    "python scripts/sign_daily_data.py",
    "python scripts/sign_update_manifest.py",
    "VERIFIED_DATA_BRANCH: verified-data",
    "environment: production-data-signing",
):
    if token not in update:
        raise SystemExit(f"Daily Update workflow is missing required token: {token}")

print("WORKFLOWS_OK files=2 build=church-prayers.yml daily=update.yml outputs=2")
