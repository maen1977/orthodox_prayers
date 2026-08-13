#!/usr/bin/env python3
"""Validate appointed-Liturgy selection and fail-closed service rendering."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("phase6_service_selector_validator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Liturgy service selection validation failed: " + message)


def main() -> None:
    update = load_updater()
    rules = json.loads((ROOT / "canonical/liturgy_service_rules.json").read_text(encoding="utf-8"))
    editions = json.loads((ROOT / "canonical/liturgy_service_editions.json").read_text(encoding="utf-8"))
    require(rules.get("fail_closed") is True, "rules must fail closed")
    require(editions.get("wrong_liturgy_fallback_allowed") is False, "wrong-rite fallback must be disabled")
    require(editions.get("machine_translation_allowed") is False, "machine translation must stay disabled")

    pascha = update.orthodox_pascha_gregorian(2026)
    require(pascha == date(2026, 4, 12), "unexpected 2026 Orthodox Pascha calculation")
    cases = [
        (pascha - timedelta(days=42), "basil"),
        (pascha - timedelta(days=3), "basil"),
        (pascha - timedelta(days=1), "basil"),
        (date(2026, 2, 25), "presanctified"),
        (pascha - timedelta(days=6), "presanctified"),
        (pascha - timedelta(days=4), "presanctified"),
        (pascha - timedelta(days=2), "no_divine_liturgy"),
        (date(2026, 7, 26), "chrysostom"),
    ]
    for civil, expected in cases:
        info = update.day_info(civil)
        selected = update.liturgy_service_selection(civil, info)
        require(selected.get("service_type") == expected, f"{civil}: expected {expected}, got {selected.get('service_type')}")
        require(bool(selected.get("service_form")), f"{civil}: service form missing")
        require(bool((selected.get("reason") or {}).get("ar")), f"{civil}: Arabic selection reason missing")
        require(selected.get("wrong_liturgy_fallback_allowed") is False, f"{civil}: selection fallback flag")
        require(selected.get("full_service_required") is True, f"{civil}: full-service requirement missing")
        service = update.build_liturgy_service("divine_liturgy", civil, info, [], "خدمة اليوم")
        require(service.get("wrong_liturgy_fallback_allowed") is False, f"{civil}: fallback flag")
        if expected in {"chrysostom", "basil", "presanctified"}:
            expected_id = {
                "chrysostom": "divine_liturgy",
                "basil": "divine_liturgy_basil",
                "presanctified": "presanctified_liturgy",
            }[expected]
            require(selected.get("displayable") is True, f"{civil}: complete appointed rite is not displayable")
            require(service.get("extends_service_id") == expected_id, f"{civil}: appointed template missing")
            require(service.get("template_id") == f"library:{expected_id}", f"{civil}: appointed template ID mismatch")
            require(service.get("full_service_complete") is True, f"{civil}: appointed service not complete")
        else:
            require("extends_service_id" not in service, f"{civil}: wrong template attached")
            require("template_id" not in service, f"{civil}: wrong template ID attached")
            require("slot_replacements" not in service, f"{civil}: liturgical slots must be absent while blocked")

    annunciation = update.julian_to_gregorian_date(2026, 3, 25)
    require(update.liturgy_service_selection(annunciation, update.day_info(annunciation)).get("service_type") == "chrysostom", "Annunciation exception")
    sunday_annunciation = update.julian_to_gregorian_date(2024, 3, 25)
    require(update.liturgy_service_selection(sunday_annunciation, update.day_info(sunday_annunciation)).get("service_type") == "basil", "Annunciation combined with a Lenten Sunday")
    friday_collision = update.julian_to_gregorian_date(2034, 3, 25)
    collision = update.liturgy_service_selection(friday_collision, update.day_info(friday_collision))
    require(collision.get("service_type") == "typikon_override_required", "Annunciation/Great-Friday collision must require an override")
    collision_service = update.build_liturgy_service("divine_liturgy", friday_collision, update.day_info(friday_collision), [], "خدمة اليوم")
    require(collision_service.get("publication_status") == "BLOCKED_REQUIRES_DATED_OFFICIAL_TYPIKON_OVERRIDE", "collision must fail closed")
    require(editions["editions"]["basil"].get("displayable") is True, "Basil complete native import must be displayable")
    require(editions["editions"]["presanctified"].get("displayable") is True, "Presanctified complete native import must be displayable")
    require(editions["editions"]["james"].get("displayable") is False, "Saint James must require dated appointment and complete native import")
    print("LITURGY_SERVICE_SELECTION_OK cases=11 forms=true reasons=true full_service=true fail_closed=true wrong_rite_fallback=false")


if __name__ == "__main__":
    main()
