#!/usr/bin/env python3
"""Run deterministic checks for the native-language, signed-data release contract."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(require_current: bool, strict_native_lanes: bool) -> list[list[str]]:
    quality = [sys.executable, "scripts/quality_check.py", "data/calendar/today.json"]
    if not require_current:
        quality.append("--allow-stale")

    checks: list[list[str]] = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        [sys.executable, "scripts/validate_workflows.py"],
        [sys.executable, "scripts/verify_gradle_wrapper.py"],
        [sys.executable, "scripts/scan_repository_secrets.py"],
        [sys.executable, "scripts/verify_static_texts.py"],
        [sys.executable, "scripts/validate_static_prayer_sources.py"],
        [sys.executable, "scripts/validate_native_language_packs.py"],
        [sys.executable, "scripts/validate_native_source_contract.py"],
        [sys.executable, "scripts/build_public_source_registry.py"],
        [sys.executable, "scripts/validate_public_source_registry.py"],
    ]
    if strict_native_lanes:
        # Strict lane integrity rejects copied Arabic and wrong-script content.
        # Completeness remains a separate production-release requirement enforced
        # by validate_release_readiness.py, so incomplete languages stay honest.
        checks.append(
            [sys.executable, "scripts/check_native_coverage.py", "--reject-invalid"]
        )
    checks.extend(
        [
            [sys.executable, "scripts/validate_daily_native_content.py"],
            [sys.executable, "scripts/validate_json_schema.py"],
            [sys.executable, "scripts/validate_embedded_app_data.py"],
            [sys.executable, "scripts/validate_reader_services.py"],
            [sys.executable, "scripts/verify_data_signature.py"],
            [sys.executable, "scripts/validate_scripture_translations.py", "data/calendar/today.json"],
            [sys.executable, "scripts/validate_content_deduplication.py"],
            [sys.executable, "scripts/validate_content_review.py"],
            [sys.executable, "scripts/validate_official_sources.py"],
            [sys.executable, "scripts/validate_jordan_liturgical_contract.py"],
            [sys.executable, "scripts/validate_no_placeholder_guidance.py"],
            [sys.executable, "scripts/validate_liturgical_schedule.py", "data/calendar/today.json"],
            [sys.executable, "scripts/validate_fasting_guidance.py", "data/calendar/today.json"],
            quality,
        ]
    )
    return checks


def main() -> None:
    args = set(sys.argv[1:])
    allowed = {"--require-current", "--strict-native-lanes"}
    unknown = args - allowed
    if unknown:
        raise SystemExit("Unknown argument(s): " + ", ".join(sorted(unknown)))

    require_current = "--require-current" in args
    strict_native_lanes = "--strict-native-lanes" in args

    # Source archives uploaded from Windows or GitHub web may lose POSIX mode
    # metadata. Normalize gradlew before tests inspect the release contract.
    permission_command = [sys.executable, "scripts/ensure_gradlew_executable.py"]
    print("\n>>> " + " ".join(permission_command), flush=True)
    subprocess.run(permission_command, cwd=ROOT, check=True)

    for command in commands(require_current, strict_native_lanes):
        print("\n>>> " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)

    date_mode = "current-signed" if require_current else "source-tree"
    lane_mode = "strict-lane-integrity" if strict_native_lanes else "basic-lane-integrity"
    print(
        "\nAll native-language, exact-text, source, workflow, Gradle-wrapper, "
        f"signed-data, and Android asset checks passed ({date_mode}; {lane_mode})."
    )


if __name__ == "__main__":
    main()
