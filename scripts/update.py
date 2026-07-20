#!/usr/bin/env python3
"""Generate and validate daily data, then optionally sign it."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


PIPELINE_PATCH_LEVEL = "R14"

def verify_pipeline_patch() -> None:
    """Fail clearly when patch files were copied into a nested folder or mixed."""
    integrity_path = ROOT / "scripts/orthodox_integrity.py"
    schedule_path = ROOT / "scripts/update_liturgical_data.py"
    integrity_text = integrity_path.read_text(encoding="utf-8")
    schedule_text = schedule_path.read_text(encoding="utf-8")
    fasting_validator_path = ROOT / "scripts/validate_fasting_guidance.py"
    home_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
    settings_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"
    required = {
        str(integrity_path.relative_to(ROOT)): "if kind == \"prokeimenon\":",
        str(schedule_path.relative_to(ROOT)): 'data["fasting_guidance_version"] = 1',
        str(fasting_validator_path.relative_to(ROOT)): "documented_interval",
        str(home_path.relative_to(ROOT)): "R14_HOME_COMPACT",
        str(settings_path.relative_to(ROOT)): "R14_SETTINGS_CLEANUP",
    }
    actual = {
        str(integrity_path.relative_to(ROOT)): integrity_text,
        str(schedule_path.relative_to(ROOT)): schedule_text,
        str(fasting_validator_path.relative_to(ROOT)): fasting_validator_path.read_text(encoding="utf-8") if fasting_validator_path.is_file() else "",
        str(home_path.relative_to(ROOT)): home_path.read_text(encoding="utf-8") if home_path.is_file() else "",
        str(settings_path.relative_to(ROOT)): settings_path.read_text(encoding="utf-8") if settings_path.is_file() else "",
    }
    missing = [name for name, marker in required.items() if marker not in actual[name]]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"PIPELINE_PATCH_MISMATCH expected={PIPELINE_PATCH_LEVEL} missing={joined}; "
            "extract the changes ZIP directly into the repository root and overwrite existing files"
        )
    print(f"PIPELINE_PATCH_OK level={PIPELINE_PATCH_LEVEL}", flush=True)


def run(*args: str, check: bool = True) -> int:
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode


def remove_stale_daily_signatures(date_iso: str) -> None:
    """Unsigned generation must never leave signatures from an older payload."""
    for path in (
        ROOT / "data/calendar/today.json.sig",
        ROOT / "app/src/main/assets/data/today.json.sig",
        ROOT / f"data/calendar/{date_iso}.json.sig",
    ):
        path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    signing = parser.add_mutually_exclusive_group(required=True)
    signing.add_argument("--private-key", type=Path)
    signing.add_argument(
        "--unsigned",
        action="store_true",
        help="Generate and validate only; remove stale signatures and sign in a later protected step.",
    )
    args = parser.parse_args()
    verify_pipeline_patch()
    os.environ["ORTHODOX_DATE"] = args.date

    if args.private_key is not None and not args.private_key.is_file():
        raise SystemExit("data-signing private key is missing")

    run("scripts/update_liturgical_data.py")
    integrity = run("scripts/orthodox_integrity.py", "--apply", check=False)
    mode = "full" if integrity == 0 else "partial"
    run("scripts/fill_daily_from_native_corpora.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Services are initially composed before native Scripture is resolved.
    # Recompose them now so the Divine Liturgy uses the same verified text as
    # the Readings screen, then re-apply lane metadata to the new overlays.
    run("scripts/rebuild_daily_services.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Never publish a new day with blank Epistle/Gospel cards. A transient
    # Scripture-source failure keeps the last signed good day instead.
    run("scripts/validate_daily_native_content.py", "data/calendar/today.json", "--require-complete")
    run("scripts/mark_partial_daily.py", "--date", args.date, "--mode", mode)

    # This is the final fail-closed local-jurisdiction gate. It is deliberately
    # executed before the generated payload is copied into the Android assets
    # or signed, so manual/non-workflow update paths cannot bypass Jordan's
    # date, Epistle, Gospel, and Divine Liturgy contract.
    run(
        "scripts/validate_jordan_liturgical_contract.py",
        "data/calendar/today.json",
        "--expected-date",
        args.date,
        "--require-jordan-authority",
        "--require-complete-liturgy",
    )

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
            ("scripts/validate_fasting_guidance.py", "data/calendar/today.json"),
            ("scripts/quality_check.py", "data/calendar/today.json"),
            ("scripts/validate_embedded_app_data.py",),
            ("scripts/validate_static_prayer_sources.py",),
            ("scripts/validate_native_language_packs.py",),
            ("scripts/validate_reader_services.py",),
            ("scripts/validate_daily_ui_localizations.py", "data/calendar/today.json"),
            ("scripts/validate_scripture_translations.py", "data/calendar/today.json"),
        ):
            run(*command)
    else:
        run("scripts/validate_partial_daily.py", "--expected-date", args.date)
        run("scripts/validate_static_prayer_sources.py")
        run("scripts/validate_reader_services.py")

    if args.unsigned:
        remove_stale_daily_signatures(args.date)
        print(f"DAILY_UPDATE_UNSIGNED_OK date={args.date} mode={mode}")
        return

    run("scripts/sign_daily_data.py", "--private-key", str(args.private_key))
    run("scripts/verify_data_signature.py")
    print(f"DAILY_UPDATE_OK date={args.date} mode={mode}")


if __name__ == "__main__":
    main()
