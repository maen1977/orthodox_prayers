#!/usr/bin/env python3
"""Validate the phase-eight finalization pipeline and report real blockers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "canonical/liturgy_phase8_completion_contract.json"
EDITIONS = ROOT / "canonical/liturgy_service_editions.json"
DAILY = ROOT / "data/calendar/today.json"
RELIGIOUS = ROOT / "canonical/religious_completeness_manifest.json"
BUILD_EVIDENCE = ROOT / "release/android/build-evidence.json"


def build_report() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    editions = json.loads(EDITIONS.read_text(encoding="utf-8"))
    daily = json.loads(DAILY.read_text(encoding="utf-8"))
    religious = json.loads(RELIGIOUS.read_text(encoding="utf-8"))
    service_ready = {
        service: bool((editions.get("editions") or {}).get(service, {}).get("displayable"))
        for service in ("chrysostom", "basil", "presanctified")
    }
    rolling = daily.get("rolling_week") or {}
    rolling_complete = (
        rolling.get("policy") == "NINE_CONSECUTIVE_DAYS_STARTING_TODAY"
        and rolling.get("day_count") == 9
        and len(daily.get("weekly_days") or []) == 8
        and rolling.get("status") == "COMPLETE"
        and rolling.get("fail_closed") is True
    )
    signed_baseline_only = contract["required_release_gates"]["signed_daily_data"]["current_status"] == "UNCHANGED_SIGNED_BASELINE_ONLY"
    build = None
    if BUILD_EVIDENCE.is_file():
        build = json.loads(BUILD_EVIDENCE.read_text(encoding="utf-8"))
    build_complete = bool(build and build.get("success") and build.get("apk_files"))
    language_services = religious.get("languages") or {}
    liturgy_states = {
        lang: {
            "chrysostom": (states or {}).get("chrysostom_liturgy"),
            "basil": (states or {}).get("basil_liturgy"),
            "presanctified": (states or {}).get("presanctified_liturgy")
        }
        for lang, states in language_services.items()
    }
    blockers = []
    for service, ready in service_ready.items():
        if not ready:
            blockers.append(f"native_service_not_displayable:{service}")
    if not rolling_complete:
        blockers.append("signed_nine_day_rolling_window_missing_or_incomplete")
    if signed_baseline_only:
        blockers.append("phase8_candidate_not_signed_with_official_key")
    if not build_complete:
        blockers.append("android_apk_build_evidence_missing")
    complete = not blockers
    return {
        "phase": "R21_PHASE8",
        "pipeline_status": contract.get("status"),
        "complete_release_allowed": complete,
        "native_service_displayable": service_ready,
        "rolling_window_complete": rolling_complete,
        "rolling_window_days": int(rolling.get("day_count") or 0),
        "annual_preload_required": False,
        "signed_phase8_candidate": not signed_baseline_only,
        "android_build_complete": build_complete,
        "language_liturgy_states": liturgy_states,
        "blockers": blockers,
        "fail_closed": True
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.require_complete and not report["complete_release_allowed"]:
        raise SystemExit("PHASE8_COMPLETE_RELEASE_BLOCKED " + ",".join(report["blockers"]))
    print(
        "PHASE8_FINALIZATION_GATE_OK "
        f"complete={str(report['complete_release_allowed']).lower()} "
        f"blockers={len(report['blockers'])} fail_closed=true"
    )


if __name__ == "__main__":
    main()
