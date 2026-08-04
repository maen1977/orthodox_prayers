#!/usr/bin/env python3
"""Validate the Android SDK compatibility and instrumentation contract."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "app/build.gradle.kts"
WORKFLOW = ROOT / ".github/workflows/build.yml"


def read_int(text: str, name: str) -> int:
    match = re.search(rf"\b{name}\s*=\s*(\d+)", text)
    if not match:
        raise SystemExit(f"{name} is missing from app/build.gradle.kts")
    return int(match.group(1))


def main() -> None:
    text = GRADLE.read_text(encoding="utf-8")
    compile_sdk = read_int(text, "compileSdk")
    min_sdk = read_int(text, "minSdk")
    target_sdk = read_int(text, "targetSdk")

    if min_sdk != 26:
        raise SystemExit(f"Android 8 security floor changed: expected minSdk=26, got {min_sdk}")
    if compile_sdk < 35 or target_sdk < 35:
        raise SystemExit(
            f"Modern Android contract requires compileSdk/targetSdk >= 35; "
            f"got compileSdk={compile_sdk}, targetSdk={target_sdk}"
        )
    if min_sdk > target_sdk or target_sdk > compile_sdk:
        raise SystemExit(
            f"Invalid SDK ordering: minSdk={min_sdk}, targetSdk={target_sdk}, compileSdk={compile_sdk}"
        )
    runner = 'testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"'
    if runner not in text:
        raise SystemExit("AndroidJUnitRunner contract is missing")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    required_runtime_contract = (
        "api-level: 35",
        "script: bash scripts/run_android_emulator_ci.sh 35",
        "api-level: 26",
        "ram-size: 1024M",
        "script: bash scripts/run_android_emulator_ci.sh 26 smoke",
        "api: [29, 33]",
        "run_android_upgrade_ci.sh 26",
        "run_android_failure_recovery_ci.sh 35",
        "needs: [android_debug, android_instrumented, android_legacy, android_compatibility, android_upgrade, android_resilience]",
    )
    missing = [value for value in required_runtime_contract if value not in workflow]
    if missing:
        raise SystemExit("Android runtime coverage is incomplete: " + ", ".join(missing))

    print(
        "ANDROID_SDK_CONTRACT_OK "
        f"minSdk={min_sdk} targetSdk={target_sdk} compileSdk={compile_sdk} "
        "runtime_emulators=26-low-memory,29,33,35-current upgrade_and_resilience_required=true"
    )


if __name__ == "__main__":
    main()
