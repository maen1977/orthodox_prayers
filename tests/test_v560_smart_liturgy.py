from __future__ import annotations

import importlib.util
import json
import os
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT_SCOPE = "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"


def updater():
    os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")
    path = ROOT / "scripts/update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("test_v560_updater", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_version_is_560():
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'versionCode = 50601' in build
    assert 'versionName = "5.6.1"' in build


def test_strict_core_contract_excludes_adjacent_offices():
    contract = json.loads((ROOT / "canonical/full_liturgy_service_contract.json").read_text(encoding="utf-8"))
    complete = contract["definition_of_complete"]
    assert complete["scope"] == STRICT_SCOPE
    assert complete["no_unappointed_material_allowed"] is True
    excluded = set(complete["excludes_as_separate_offices"])
    assert "orthros_and_matins_gospel" in excluded
    assert "proskomide" in excluded
    assert "personal_pre_communion_prayers" in excluded
    assert "thanksgiving_after_communion" in excluded


def test_only_chrysostom_is_publishable_across_all_three_native_lanes():
    editions = json.loads((ROOT / "canonical/liturgy_service_editions.json").read_text(encoding="utf-8"))["editions"]
    assert editions["chrysostom"]["displayable"] is True
    assert editions["basil"]["displayable"] is False
    assert "OCR_CORRUPTION" in editions["basil"]["ar"]
    assert "REIMPORT_REQUIRED" in editions["basil"]["el"]
    assert editions["presanctified"]["displayable"] is False
    assert "EXPLANATORY_EXCERPT_NOT_FULL_SERVICE" in editions["presanctified"]["ar"]


def test_calendar_selects_rite_but_never_substitutes_blocked_rite():
    u = updater()
    pascha = u.orthodox_pascha_gregorian(2026)
    for day, kind, form in [
        (pascha - timedelta(days=3), "basil", "vespers_with_divine_liturgy"),
        (pascha - timedelta(days=4), "presanctified", "lenten_vespers_with_presanctified"),
        (pascha - timedelta(days=2), "no_divine_liturgy", "no_divine_liturgy"),
    ]:
        info = u.day_info(day)
        sel = u.liturgy_service_selection(day, info)
        svc = u.build_liturgy_service("divine_liturgy", day, info, [], "خدمة اليوم")
        assert sel["service_type"] == kind
        assert sel["service_form"] == form
        assert sel["wrong_liturgy_fallback_allowed"] is False
        assert "extends_service_id" not in svc
        assert svc["full_service_complete"] is False


def test_chrysostom_day_uses_only_liturgy_slots_not_matins():
    u = updater()
    day = date(2026, 7, 26)
    info = u.day_info(day)
    svc = u.build_liturgy_service("divine_liturgy", day, info, [], "خدمة اليوم")
    assert svc["selected_liturgy_type"] == "chrysostom"
    assert svc["full_service_scope"] == STRICT_SCOPE
    assert svc["liturgy_day_plan"]["strict_core_only"] is True
    assert svc["liturgy_day_plan"]["orthros_separate"]["belongs_to"] == "orthros_not_divine_liturgy"
    assert "matins_gospel" not in svc["slot_replacements"]
    assert svc["extends_service_id"] == "divine_liturgy"


def test_android_reader_does_not_merge_adjacent_offices_into_liturgy():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    composer = source.split("private JSONObject composeFollowAlongLiturgy", 1)[1].split("private static JSONArray strictAppointedLiturgyCore", 1)[0]
    assert "STRICT_APPOINTED_LITURGY_CORE_ONLY" in composer
    assert STRICT_SCOPE in composer
    assert "thanksgivingSegmentsForLiturgy" not in composer
    assert "findServiceInArray(library().optJSONArray(\"services\"), \"pre_communion_prayers\")" not in composer
    assert '"matins_gospel".equals(copy.optString("dynamic_slot", ""))' in source


def test_local_engine_never_prewires_chrysostom_for_blocked_rite():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java").read_text(encoding="utf-8")
    assert 'if (!liturgy) service.put("extends_service_id", baseId);' in source
    assert 'service.remove("extends_service_id")' in source
    assert '"lenten_vespers_with_presanctified".equals(form)' in source
    assert '"APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"' in source
