#!/usr/bin/env python3
"""Release gate for the network-free Android Daily Update architecture."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    [sys.executable, "scripts/simple_quality_gate.py"],
    [sys.executable, "scripts/validate_full_church_services.py"],
    [sys.executable, "scripts/verify_r17_patch.py"],
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_local_daily_engine.py",
        "tests/test_r17_update_reliability.py",
        "tests/test_follow_along_liturgy.py",
        "tests/test_internal_calendar_2050.py",
        "tests/test_app_update_github_delivery.py",
        "tests/test_ui_localizations.py",
        "tests/test_v510_reader_experience.py",
        "tests/test_runtime_asset_budget.py",
        "tests/test_reader_service_pruning.py",
        "tests/test_user_reported_liturgy_and_home_regressions.py",
        "tests/test_v550_full_church_services.py",
        "tests/test_prepare_church_service_corpus.py",
        "tests/test_v560_smart_liturgy.py",
        "tests/test_r24_nine_day_liturgy_engine.py",
    ],
]


def main() -> None:
    for command in COMMANDS:
        print("\n>>> " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    print(
        "\nLOCAL_DAILY_RELEASE_GATE_OK "
        "version=5.6.4 code=50604 schedule=00:03 timezone=Asia/Amman "
        "network_required=false github_daily_action=false calendar=2026-2050"
    )


if __name__ == "__main__":
    main()
