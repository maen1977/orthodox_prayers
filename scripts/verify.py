#!/usr/bin/env python3
"""Single health check for the published verified-data branch."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    args = parser.parse_args()
    payload = ROOT / "data/calendar/today.json"
    data = json.loads(payload.read_text(encoding="utf-8"))
    if data.get("date_iso") != args.expected_date:
        raise SystemExit(f"published date {data.get('date_iso')!r} != {args.expected_date!r}")
    run("scripts/verify_data_signature.py")
    run("scripts/validate_partial_daily.py", "--expected-date", args.expected_date)
    run("scripts/verify_language_lanes.py", "--date", args.expected_date)
    run("scripts/validate_publication_consistency.py", "--expected-date", args.expected_date)
    run("scripts/verify_update_manifest.py", "--expected-date", args.expected_date)
    print(f"PUBLISHED_DAILY_OK date={args.expected_date}")

if __name__ == "__main__":
    main()
