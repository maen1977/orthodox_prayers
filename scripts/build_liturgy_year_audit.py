#!/usr/bin/env python3
"""Build a deterministic day-by-day Liturgy coverage audit without network access."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("phase9_year_audit_updater", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def localized_complete(value: Any) -> bool:
    return isinstance(value, dict) and all(str(value.get(lang) or "").strip() for lang in LANGS)


def reading_by_kind(readings: list[dict], kind: str) -> dict:
    return next((item for item in readings if isinstance(item, dict) and item.get("kind") == kind), {})


def reading_complete(reading: dict) -> bool:
    if not isinstance(reading, dict):
        return False
    body = reading.get("body")
    reference = reading.get("reference")
    return localized_complete(body) and localized_complete(reference)


def audit_day(update, day: date) -> dict:
    info = update.day_info(day)
    selection = update.liturgy_service_selection(day, info)
    acquisition_errors: list[str] = []
    try:
        readings = update.discovery_readings(day, info)
    except Exception as exc:
        readings = []
        acquisition_errors.append(f"reading_resolution_error:{type(exc).__name__}")
    try:
        inserts = update.feast_inserts(info, day)
    except Exception as exc:
        inserts = {
            "proper_id": None, "proper_provenance": "error", "resurrection_tone": None, "eothinon": None,
            "troparion": {}, "kontakion": {}, "communion": {},
        }
        acquisition_errors.append(f"proper_resolution_error:{type(exc).__name__}")
    selected_type = str(selection.get("service_type") or "")
    blockers: list[str] = list(acquisition_errors)

    if selected_type == "typikon_override_required":
        blockers.append("dated_typikon_override_required")
    elif selected_type not in {"no_divine_liturgy"} and not bool(selection.get("displayable")):
        blockers.append(f"native_service_not_displayable:{selected_type}")

    if selected_type != "no_divine_liturgy":
        for kind in ("epistle", "gospel"):
            if not reading_complete(reading_by_kind(readings, kind)):
                blockers.append(f"reading_incomplete:{kind}")
        if day.weekday() == 6 and not reading_complete(reading_by_kind(readings, "matins_gospel")):
            blockers.append("reading_incomplete:matins_gospel")

        for slot in ("troparion", "kontakion", "prokeimenon", "communion"):
            if slot == "prokeimenon":
                value = reading_by_kind(readings, "prokeimenon").get("body")
            else:
                value = inserts.get(slot)
            if not localized_complete(value):
                blockers.append(f"proper_incomplete:{slot}")

    dated = update.dated_liturgical_proper_entry(day)
    provenance = "dated" if dated else str(inserts.get("proper_provenance") or "ordinary")
    return {
        "date": day.isoformat(),
        "julian_date": f"{info['julian_year']:04d}-{info['julian_month']:02d}-{info['julian_day']:02d}",
        "weekday": day.weekday(),
        "is_sunday": day.weekday() == 6,
        "service_type": selected_type,
        "service_rule_id": selection.get("rule_id"),
        "service_displayable": bool(selection.get("displayable")),
        "proper_id": inserts.get("proper_id"),
        "proper_provenance": provenance,
        "resurrection_tone": inserts.get("resurrection_tone"),
        "eothinon": inserts.get("eothinon"),
        "complete_for_release": not blockers,
        "blockers": blockers,
        "fail_closed": True,
    }


def build_report(year: int, phase: str = "R21_PHASE11") -> dict:
    os.environ["ORTHODOX_DISABLE_DISCOVERY_NETWORK"] = "1"
    update = load_updater()
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    days: list[dict] = []
    current = start
    while current < end:
        days.append(audit_day(update, current))
        current += timedelta(days=1)
    blocker_counts = Counter(blocker for item in days for blocker in item["blockers"])
    service_counts = Counter(item["service_type"] for item in days)
    complete_days = sum(bool(item["complete_for_release"]) for item in days)
    return {
        "schema_version": 1,
        "phase": phase,
        "year": year,
        "calendar": "civil_with_julian_old_calendar_context",
        "network_fetch_used": False,
        "expected_days": (end - start).days,
        "audited_days": len(days),
        "complete_days": complete_days,
        "incomplete_days": len(days) - complete_days,
        "annual_complete": complete_days == len(days),
        "service_type_counts": dict(sorted(service_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "days": days,
        "completion_claim": "proven_complete" if complete_days == len(days) else "unproven_complete",
        "fail_closed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", default="R21_PHASE11")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = build_report(args.year, phase=args.phase)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.require_complete and not report["annual_complete"]:
        raise SystemExit(f"LITURGY_YEAR_AUDIT_INCOMPLETE days={report['incomplete_days']}")
    print(
        "LITURGY_YEAR_AUDIT_OK "
        f"year={args.year} days={report['audited_days']} complete={report['complete_days']} "
        f"incomplete={report['incomplete_days']} fail_closed=true"
    )


if __name__ == "__main__":
    main()
