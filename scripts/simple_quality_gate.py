#!/usr/bin/env python3
"""Small, strict gate for the app build and separate daily update workflows."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    [sys.executable, "scripts/keep_required_workflows.py"],
    [sys.executable, "scripts/ensure_gradlew_executable.py"],
    [sys.executable, "scripts/validate_workflows.py"],
    [sys.executable, "scripts/validate_android_sdk_contract.py"],
    [sys.executable, "scripts/validate_calendar_immutability.py"],
    [sys.executable, "scripts/validate_internal_calendar_2050.py"],
    [sys.executable, "scripts/validate_strict_religious_content.py", "data/calendar/today.json", "--require-complete"],
    [sys.executable, "scripts/validate_divine_liturgy_text_integrity.py"],
    [sys.executable, "scripts/validate_divine_liturgy_delivery_integrity.py"],
    [sys.executable, "scripts/validate_service_edition_evidence.py"],
    [sys.executable, "scripts/validate_ui_localizations.py"],
    [sys.executable, "scripts/validate_android_resources.py"],
    [sys.executable, "scripts/validate_embedded_app_data.py"],
    [sys.executable, "scripts/verify_data_signature.py"],
    [sys.executable, "scripts/scan_repository_secrets.py"],
]


def main() -> None:
    for command in CHECKS:
        print(">>> " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    print("CHURCH_PRAYERS_CHECKS_OK")


if __name__ == "__main__":
    main()
