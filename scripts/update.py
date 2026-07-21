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


PIPELINE_PATCH_LEVEL = "R18"

def verify_pipeline_patch() -> None:
    """Fail clearly when patch files were copied into a nested folder or mixed."""
    integrity_path = ROOT / "scripts/orthodox_integrity.py"
    schedule_path = ROOT / "scripts/update_liturgical_data.py"
    integrity_text = integrity_path.read_text(encoding="utf-8")
    schedule_text = schedule_path.read_text(encoding="utf-8")
    fasting_validator_path = ROOT / "scripts/validate_fasting_guidance.py"
    home_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
    settings_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"
    sources_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SourcesScreen.java"
    coordinator_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java"
    repository_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"
    workflow_path = ROOT / ".github/workflows/update.yml"
    required = {
        str(integrity_path.relative_to(ROOT)): "if kind == \"prokeimenon\":",
        str(schedule_path.relative_to(ROOT)): 'data["fasting_guidance_version"] = 1',
        str(fasting_validator_path.relative_to(ROOT)): "documented_interval",
        str(home_path.relative_to(ROOT)): "R15_THEME_PALETTE_IMPORT",
        str(settings_path.relative_to(ROOT)): "host.navigate(\"sources\", null)",
        str(sources_path.relative_to(ROOT)): "المصادر والمراجع",
        str(coordinator_path.relative_to(ROOT)): "DAILY_REFRESH_MINUTE = 5",
        str(repository_path.relative_to(ROOT)): "downloadManifestSelection",
        str(workflow_path.relative_to(ROOT)): "ORTHODOX_ENABLE_LIVE_SOURCE_FETCH",
        "canonical/source_connectors.json": "local_authority_source_id",
        "scripts/source_connectors.py": "source_consensus",
    }
    actual = {
        str(integrity_path.relative_to(ROOT)): integrity_text,
        str(schedule_path.relative_to(ROOT)): schedule_text,
        str(fasting_validator_path.relative_to(ROOT)): fasting_validator_path.read_text(encoding="utf-8") if fasting_validator_path.is_file() else "",
        str(home_path.relative_to(ROOT)): home_path.read_text(encoding="utf-8") if home_path.is_file() else "",
        str(settings_path.relative_to(ROOT)): settings_path.read_text(encoding="utf-8") if settings_path.is_file() else "",
        str(sources_path.relative_to(ROOT)): sources_path.read_text(encoding="utf-8") if sources_path.is_file() else "",
        str(coordinator_path.relative_to(ROOT)): coordinator_path.read_text(encoding="utf-8") if coordinator_path.is_file() else "",
        str(repository_path.relative_to(ROOT)): repository_path.read_text(encoding="utf-8") if repository_path.is_file() else "",
        str(workflow_path.relative_to(ROOT)): workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else "",
        "canonical/source_connectors.json": (ROOT / "canonical/source_connectors.json").read_text(encoding="utf-8"),
        "scripts/source_connectors.py": (ROOT / "scripts/source_connectors.py").read_text(encoding="utf-8"),
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
    live_sources = os.getenv("ORTHODOX_ENABLE_LIVE_SOURCE_FETCH", "").strip() == "1"
    source_mode = [] if live_sources else ["--offline"]
    run("scripts/collect_source_health.py", "--date", args.date, *source_mode)
    run("scripts/build_church_directory.py", "--date", args.date, *source_mode)
    run("scripts/build_public_source_registry.py")
    run("scripts/validate_public_source_registry.py")

    if args.private_key is not None and not args.private_key.is_file():
        raise SystemExit("data-signing private key is missing")

    run("scripts/update_liturgical_data.py")
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    integrity = run("scripts/orthodox_integrity.py", "--apply", check=False)
    mode = "full" if integrity == 0 else "partial"
    run("scripts/fill_daily_from_native_corpora.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Services are initially composed before native Scripture is resolved.
    # Recompose them now so the Divine Liturgy uses the same verified text as
    # the Readings screen, then re-apply lane metadata to the new overlays.
    run("scripts/rebuild_daily_services.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Recalculate service completeness after the final native-language overlays are composed.
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
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
            ("scripts/validate_public_source_registry.py",),
            ("scripts/validate_source_intelligence.py", "data/calendar/today.json", "--expected-date", args.date),
            ("scripts/validate_reader_services.py",),
            ("scripts/validate_daily_ui_localizations.py", "data/calendar/today.json"),
            ("scripts/validate_scripture_translations.py", "data/calendar/today.json"),
        ):
            run(*command)
    else:
        run("scripts/validate_partial_daily.py", "--expected-date", args.date)
        run("scripts/validate_static_prayer_sources.py")
        run("scripts/validate_reader_services.py")
        run("scripts/validate_public_source_registry.py")
        run("scripts/validate_source_intelligence.py", "data/calendar/today.json", "--expected-date", args.date)

    # data/calendar is a publication alias directory, not a historical archive.
    # Keep only today.json and the current dated fallback so rsync --delete also
    # removes stale aliases from verified-data before the consistency gate runs.
    # Historical language-lane payloads remain under data/daily/YYYY-MM-DD/.
    run("scripts/clean_legacy_calendar_snapshots.py")

    if args.unsigned:
        remove_stale_daily_signatures(args.date)
        print(f"DAILY_UPDATE_UNSIGNED_OK date={args.date} mode={mode}")
        return

    run("scripts/sign_daily_data.py", "--private-key", str(args.private_key))
    run("scripts/verify_data_signature.py")
    print(f"DAILY_UPDATE_OK date={args.date} mode={mode}")


if __name__ == "__main__":
    main()
