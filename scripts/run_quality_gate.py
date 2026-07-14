#!/usr/bin/env python3
"""Run deterministic checks for the native-language, signed-data release contract."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(require_current: bool) -> list[list[str]]:
    quality = [sys.executable, "scripts/quality_check.py", "data/calendar/today.json"]
    if not require_current:
        quality.append("--allow-stale")
    return [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        [sys.executable, "scripts/validate_workflows.py"],
        [sys.executable, "scripts/scan_repository_secrets.py"],
        [sys.executable, "scripts/verify_static_texts.py"],
        [sys.executable, "scripts/validate_static_prayer_sources.py"],
        [sys.executable, "scripts/validate_native_language_packs.py"],
        [sys.executable, "scripts/validate_native_source_contract.py"],
        [sys.executable, "scripts/validate_daily_native_content.py"],
        [sys.executable, "scripts/validate_json_schema.py"],
        [sys.executable, "scripts/validate_embedded_app_data.py"],
        [sys.executable, "scripts/validate_reader_services.py"],
        [sys.executable, "scripts/verify_data_signature.py"],
        [sys.executable, "scripts/validate_scripture_translations.py", "data/calendar/today.json"],
        [sys.executable, "scripts/validate_content_deduplication.py"],
        [sys.executable, "scripts/validate_content_review.py"],
        [sys.executable, "scripts/validate_official_sources.py"],
        [sys.executable, "scripts/validate_no_placeholder_guidance.py"],
        [sys.executable, "scripts/validate_liturgical_schedule.py", "data/calendar/today.json"],
        quality,
    ]


def main() -> None:
    args = set(sys.argv[1:])
    allowed = {"--require-current", "--strict-native-lanes"}
    unknown = args - allowed
    if unknown:
        raise SystemExit("Unknown argument(s): " + ", ".join(sorted(unknown)))
    require_current = "--require-current" in args
    for command in commands(require_current):
        print("\n>>> " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    mode = "current-signed" if require_current else "source-tree"
    print(f"\nAll native-language, exact-text, source, workflow, signed-data, and Android asset checks passed ({mode}).")


if __name__ == "__main__":
    main()
