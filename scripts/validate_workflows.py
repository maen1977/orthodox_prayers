#!/usr/bin/env python3
"""Validate the intentionally simple, single GitHub workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {"church-prayers.yml"}

files = {path.name for path in WORKFLOWS.glob("*.yml")}
if files != EXPECTED:
    raise SystemExit(f"Expected one workflow {sorted(EXPECTED)}, found {sorted(files)}")

text = (WORKFLOWS / "church-prayers.yml").read_text(encoding="utf-8")
required = (
    "name: Church Prayers",
    "jobs:",
    "build:",
    "name: Build Church Prayers",
    "python scripts/keep_one_workflow.py",
    "python scripts/simple_quality_gate.py",
    "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease",
    "output/Church-Prayers.apk",
    "output/Church-Prayers.aab",
    "name: Church-Prayers",
)
for token in required:
    if token not in text:
        raise SystemExit(f"Single workflow is missing required token: {token}")

for forbidden in (
    "android-emulator-runner",
    "strategy:",
    "matrix:",
    "play-store-screenshots",
    "weekly-release-health",
    "Rolling Liturgical Window Update",
):
    if forbidden in text:
        raise SystemExit(f"Single workflow still contains unnecessary complexity: {forbidden}")

print("WORKFLOW_SIMPLE_OK files=1 jobs=1 outputs=2")
