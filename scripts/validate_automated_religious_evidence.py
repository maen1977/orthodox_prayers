#!/usr/bin/env python3
"""One fail-closed gate replacing manual review in the publication path."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days", default="9")
    parser.add_argument("--daily", default="data/calendar/today.json")
    parser.add_argument("--language", choices=("ar", "en", "el"))
    parser.add_argument("--strict-source-confirmation", action="store_true")
    args = parser.parse_args()

    rolling = [
        "scripts/validate_rolling_week.py",
        args.daily,
        "--expected-start",
        args.start_date,
    ]
    if args.language:
        rolling.extend(["--language", args.language])
    run(*rolling)

    comparison = [
        "scripts/validate_source_comparison.py",
        "--start-date",
        args.start_date,
        "--days",
        args.days,
    ]
    if args.strict_source_confirmation:
        comparison.append("--require-no-internal-failsafe")
    run(*comparison)
    run("scripts/validate_jordan_liturgical_contract.py", args.daily, "--expected-date", args.start_date, "--require-jordan-authority", "--require-complete-liturgy")
    source_intelligence = [
        "scripts/validate_source_intelligence.py",
        args.daily,
        "--expected-date",
        args.start_date,
    ]
    native_content = ["scripts/validate_daily_native_content.py", args.daily, "--require-complete"]
    scripture_policy = ["scripts/validate_scripture_translations.py", args.daily]
    if args.language:
        source_intelligence.extend(["--language", args.language])
        native_content.extend(["--language", args.language])
        scripture_policy.extend(["--language", args.language])
    run(*source_intelligence)
    run(*native_content)
    run(*scripture_policy)
    print(
        f"AUTOMATED_RELIGIOUS_EVIDENCE_OK start={args.start_date} days={args.days} "
        f"language={args.language or 'all'} human_review_required=false"
    )


if __name__ == "__main__":
    main()
