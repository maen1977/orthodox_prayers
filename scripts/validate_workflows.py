#!/usr/bin/env python3
"""Validate the one visible Church Prayers workflow and its two simple modes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {"church-prayers.yml"}

files = {path.name for pattern in ("*.yml", "*.yaml") for path in WORKFLOWS.glob(pattern)}
if files != EXPECTED:
    raise SystemExit(f"Expected one workflow {sorted(EXPECTED)}, found {sorted(files)}")

text = (WORKFLOWS / "church-prayers.yml").read_text(encoding="utf-8")
required = (
    "name: Church Prayers",
    "schedule:",
    "options: [build, update, verify]",
    "build:",
    "name: Build Church Prayers",
    "daily:",
    "name: Update Daily Prayers",
    "python scripts/simple_quality_gate.py",
    "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease",
    "python scripts/update.py",
    "python scripts/update_language_lane.py --language ar",
    "python scripts/update_language_lane.py --language el",
    "python scripts/update_language_lane.py --language en",
    "python scripts/sign_daily_data.py",
    "python scripts/sign_update_manifest.py",
    "VERIFIED_DATA_BRANCH: verified-data",
    "output/Church-Prayers.apk",
    "output/Church-Prayers.aab",
    "name: Church-Prayers",
)
for token in required:
    if token not in text:
        raise SystemExit(f"Church Prayers workflow is missing required token: {token}")

for forbidden in (
    "android-emulator-runner",
    "strategy:",
    "matrix:",
    "play-store-screenshots",
    "Weekly Release Health",
    "Play Internal Testing",
):
    if forbidden in text:
        raise SystemExit(f"Church Prayers workflow still contains unnecessary visible complexity: {forbidden}")

print("WORKFLOW_SIMPLE_OK files=1 modes=build,daily outputs=2")
