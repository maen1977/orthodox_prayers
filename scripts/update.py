#!/usr/bin/env python3
"""Single entry point for generating, validating, signing, and preparing daily data."""
from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(*args: str, check: bool = True) -> int:
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--private-key", required=True, type=Path)
    args = parser.parse_args()
    os.environ["ORTHODOX_DATE"] = args.date
    if not args.private_key.is_file():
        raise SystemExit("data-signing private key is missing")

    run("scripts/update_liturgical_data.py")
    integrity = run("scripts/orthodox_integrity.py", "--apply", check=False)
    mode = "full" if integrity == 0 else "partial"
    run("scripts/fill_daily_from_native_corpora.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/mark_partial_daily.py", "--date", args.date, "--mode", mode)

    asset = ROOT / "app/src/main/assets/data/today.json"
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data/calendar/today.json", asset)
    run("scripts/build_search_index.py")

    if mode == "full":
        for command in (
            ("scripts/validate_native_source_contract.py",),
            ("scripts/validate_daily_native_content.py",),
            ("scripts/validate_official_sources.py",),
            ("scripts/validate_no_placeholder_guidance.py",),
            ("scripts/validate_json_schema.py",),
            ("scripts/validate_liturgical_schedule.py", "data/calendar/today.json"),
            ("scripts/quality_check.py", "data/calendar/today.json"),
            ("scripts/validate_embedded_app_data.py",),
            ("scripts/validate_static_prayer_sources.py",),
            ("scripts/validate_native_language_packs.py",),
            ("scripts/validate_reader_services.py",),
            ("scripts/validate_scripture_translations.py", "data/calendar/today.json"),
        ):
            run(*command)
    else:
        run("scripts/validate_partial_daily.py", "--expected-date", args.date)
        run("scripts/validate_static_prayer_sources.py")
        run("scripts/validate_reader_services.py")

    run("scripts/sign_daily_data.py", "--private-key", str(args.private_key))
    run("scripts/verify_data_signature.py")
    print(f"DAILY_UPDATE_OK date={args.date} mode={mode}")

if __name__ == "__main__":
    main()
