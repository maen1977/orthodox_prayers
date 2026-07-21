#!/usr/bin/env python3
"""Single health check for the published verified-data branch."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    parser.add_argument(
        "--allow-missing-manifest",
        action="store_true",
        help="Permit a legacy branch with neither manifest payload nor signature. Invalid or partial manifests still fail.",
    )
    args = parser.parse_args()

    payload = ROOT / "data/calendar/today.json"
    data = json.loads(payload.read_text(encoding="utf-8"))
    if data.get("date_iso") != args.expected_date:
        raise SystemExit(f"published date {data.get('date_iso')!r} != {args.expected_date!r}")

    run("scripts/verify_data_signature.py")
    run("scripts/validate_partial_daily.py", "--expected-date", args.expected_date)
    run("scripts/verify_language_lanes.py", "--date", args.expected_date)
    run("scripts/validate_publication_consistency.py", "--expected-date", args.expected_date)

    manifest = ROOT / "data/update-manifest.json"
    manifest_signature = ROOT / "data/update-manifest.json.sig"
    if args.allow_missing_manifest and not manifest.exists() and not manifest_signature.exists():
        print("LEGACY_UPDATE_MANIFEST_ABSENT accepted_for_debug_import=true")
    else:
        run("scripts/verify_update_manifest.py", "--expected-date", args.expected_date)

    print(f"PUBLISHED_DAILY_OK date={args.expected_date}")


if __name__ == "__main__":
    main()
