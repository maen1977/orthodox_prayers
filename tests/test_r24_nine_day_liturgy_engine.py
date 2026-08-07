from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("r24_liturgy_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


UPDATE = load_updater()


def selection(day: date) -> dict:
    return UPDATE.liturgy_service_selection(day, UPDATE.day_info(day))


def test_ordinary_day_selects_chrysostom_with_reason_and_morning_form():
    selected = selection(date(2026, 7, 26))
    assert selected["service_type"] == "chrysostom"
    assert selected["service_form"] == "morning_divine_liturgy"
    assert selected["rule_id"] == "ordinary_chrysostom_baseline"
    assert selected["reason"]["ar"]
    assert selected["displayable"] is True
    assert selected["wrong_liturgy_fallback_allowed"] is False


def test_first_five_lenten_sundays_select_basil_and_never_substitute_chrysostom():
    pascha = UPDATE.orthodox_pascha_gregorian(2026)
    for offset in (-42, -35, -28, -21, -14):
        day = pascha + timedelta(days=offset)
        selected = selection(day)
        service = UPDATE.build_liturgy_service("divine_liturgy", day, UPDATE.day_info(day), [], "خدمة اليوم")
        assert selected["service_type"] == "basil"
        assert selected["service_form"] == "morning_divine_liturgy"
        assert selected["displayable"] is False
        assert service["full_service_complete"] is False
        assert service["publication_status"] == "BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION"
        assert "extends_service_id" not in service
        assert service["wrong_liturgy_fallback_allowed"] is False


def test_holy_thursday_and_saturday_select_vesperal_basil():
    pascha = UPDATE.orthodox_pascha_gregorian(2026)
    for offset in (-3, -1):
        selected = selection(pascha + timedelta(days=offset))
        assert selected["service_type"] == "basil"
        assert selected["service_form"] == "vespers_with_divine_liturgy"


def test_lenten_wednesday_and_holy_week_days_select_presanctified_form():
    pascha = UPDATE.orthodox_pascha_gregorian(2026)
    dates = [date(2026, 2, 25), pascha - timedelta(days=6), pascha - timedelta(days=4)]
    for day in dates:
        selected = selection(day)
        assert selected["service_type"] == "presanctified"
        assert selected["service_form"] == "lenten_vespers_with_presanctified"
        assert selected["displayable"] is False


def test_great_friday_is_explicit_no_liturgy_state():
    day = UPDATE.orthodox_pascha_gregorian(2026) - timedelta(days=2)
    selected = selection(day)
    service = UPDATE.build_liturgy_service("divine_liturgy", day, UPDATE.day_info(day), [], "خدمة اليوم")
    assert selected["service_type"] == "no_divine_liturgy"
    assert selected["service_form"] == "no_divine_liturgy"
    assert service["publication_status"] == "NO_DIVINE_LITURGY_APPOINTED"
    assert service["full_service_complete"] is False
    assert "extends_service_id" not in service


def test_saint_james_requires_dated_documented_override_and_stays_blocked_without_editions():
    day = date(2026, 10, 23)
    info = UPDATE.day_info(day)
    info["liturgy_service_override"] = {
        "service_type": "james",
        "evidence": {
            "status": "DOCUMENTED_OVERRIDE",
            "source_id": "dated_diocesan_typikon",
            "source_url": "https://example.invalid/dated-official-ruling",
        },
    }
    selected = UPDATE.liturgy_service_selection(day, info)
    service = UPDATE.build_liturgy_service("divine_liturgy", day, info, [], "خدمة اليوم")
    assert selected["service_type"] == "james"
    assert selected["rule_id"] == "dated_official_jordan_override"
    assert selected["displayable"] is False
    assert service["publication_status"] == "BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION"
    assert "extends_service_id" not in service


def test_undocumented_override_is_rejected():
    day = date(2026, 10, 23)
    info = UPDATE.day_info(day)
    info["liturgy_service_override"] = {
        "service_type": "james",
        "evidence": {"status": "UNVERIFIED", "source_id": "x", "source_url": "https://example.invalid"},
    }
    try:
        UPDATE.liturgy_service_selection(day, info)
    except RuntimeError as exc:
        assert "DOCUMENTED_OVERRIDE" in str(exc)
    else:
        raise AssertionError("undocumented override must fail closed")


def test_complete_chrysostom_overlay_declares_beginning_to_end_contract():
    day = date(2026, 7, 26)
    service = UPDATE.build_liturgy_service("divine_liturgy", day, UPDATE.day_info(day), [], "خدمة اليوم")
    assert service["selected_liturgy_type"] == "chrysostom"
    assert service["full_service_complete"] is True
    assert service["publication_status"] == "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END"
    assert service["wrong_liturgy_fallback_allowed"] is False
    contract = service["liturgy_service_contract"]
    assert contract["full_service_scope"] == "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"
    assert service["extends_service_id"] == "divine_liturgy"


def test_android_reader_keeps_adjacent_offices_separate_from_liturgy():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    composer = source.split("private JSONObject composeFollowAlongLiturgy", 1)[1].split("private static JSONArray strictAppointedLiturgyCore", 1)[0]
    assert "STRICT_APPOINTED_LITURGY_CORE_ONLY" in composer
    assert "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL" in composer
    assert 'follow_along_mode' in source
    assert 'full_service_complete' in source
    assert 'findServiceInArray(library().optJSONArray("services"), "pre_communion_prayers")' not in composer
    assert 'thanksgivingSegmentsForLiturgy' not in composer


def test_ui_exposes_type_form_reason_and_complete_open_action():
    upcoming = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java").read_text(encoding="utf-8")
    calendar = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java").read_text(encoding="utf-8")
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    for source in (upcoming, calendar):
        assert "ui_appointed_liturgy_label" in source
        assert "ui_service_form_label" in source
        assert "ui_selection_reason_label" not in source
    assert "ui_open_complete_service_beginning_to_end" in calendar
    assert "ui_open_full_appointed_liturgy_format" in home


def test_full_service_contract_is_fail_closed_for_every_published_language():
    contract = json.loads((ROOT / "canonical/full_liturgy_service_contract.json").read_text(encoding="utf-8"))
    complete = contract["definition_of_complete"]
    assert contract["rolling_window"]["default_day_count"] == 9
    assert contract["rolling_window"]["minimum_day_count"] == 9
    assert contract["rolling_window"]["maximum_day_count"] == 9
    assert complete["partial_text_allowed"] is False
    assert complete["cross_language_fallback_allowed"] is False
    assert complete["wrong_rite_fallback_allowed"] is False
    assert set(contract["blocked_until_complete_native_import"]) == {"basil", "presanctified", "james"}


def test_production_release_gate_uses_moving_horizon_not_annual_preload():
    source = (ROOT / "scripts/validate_release_readiness.py").read_text(encoding="utf-8")
    assert "metadata_errors" in source
    assert "ROLLING_FUTURE_WINDOW" in (ROOT / "scripts/rolling_window_contract.py").read_text(encoding="utf-8")
    assert "validate_full_liturgy_services.py" in source
    assert "wrong-rite substitution is forbidden" in source.lower()
    assert "liturgy_annual_coverage" not in source
    assert "annual_variable_parts" not in source
    phase8 = json.loads((ROOT / "canonical/liturgy_phase8_completion_contract.json").read_text(encoding="utf-8"))
    rolling = phase8["required_release_gates"]["rolling_liturgical_window"]
    assert rolling["default_day_count"] == 9
    assert rolling["minimum_day_count"] == 9
    assert rolling["maximum_day_count"] == 9
    assert rolling["annual_preload_required"] is False


def test_android_accepts_new_schema_ten_and_legacy_schema_nine():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataContract.java").read_text(encoding="utf-8")
    assert "MIN_SUPPORTED_SCHEMA_VERSION = 9" in source
    assert "MAX_SUPPORTED_SCHEMA_VERSION = 10" in source
