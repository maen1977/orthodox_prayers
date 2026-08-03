#!/usr/bin/env python3
"""Validate the Android SDK compatibility and instrumentation contract."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "app/build.gradle.kts"


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

    if min_sdk > 29:
        raise SystemExit(f"minSdk={min_sdk} no longer covers Android 10/API 29")
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

    print(
        "ANDROID_SDK_CONTRACT_OK "
        f"minSdk={min_sdk} targetSdk={target_sdk} compileSdk={compile_sdk} "
        "runtime_emulator_api=35 legacy_runtime_coverage=lint"
    )


if __name__ == "__main__":
    main()
