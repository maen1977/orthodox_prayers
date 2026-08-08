#!/usr/bin/env python3
"""R56 strict appointed-Liturgy audit.

This validator deliberately separates two questions:
1. Does the calendar select the right *rite/form* fail-closed?
2. Is that rite's native text genuinely publishable in every app language?

It never promotes a service because it is merely large.  Known OCR corruption,
an explanatory excerpt, cross-language fallback, or a missing native lane keeps
that rite blocked.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
STRICT_SCOPE = "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_updater():
    os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("r56_smart_liturgy_updater", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def service_index(language: str) -> dict[str, dict]:
    payload = load_json(ROOT / f"app/src/main/assets/data/native/library_{language}.json")
    return {str(s.get("id") or ""): s for s in payload.get("services", []) if isinstance(s, dict)}


def lane_text(service: dict, language: str) -> str:
    pieces: list[str] = []
    for seg in service.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        for key in ("title", "speaker", "text"):
            obj = seg.get(key)
            if isinstance(obj, dict):
                value = str(obj.get(language) or "").strip()
                if value:
                    pieces.append(value)
    return "\n".join(pieces)


def text_stats(service: dict, language: str) -> tuple[int, int]:
    count = 0
    chars = 0
    for seg in service.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        obj = seg.get("title") if seg.get("type") == "section" else seg.get("text")
        if isinstance(obj, dict):
            value = str(obj.get(language) or "").strip()
            if value:
                count += 1
                chars += len(value)
    return count, chars


def require(ok: bool, message: str, errors: list[str]) -> None:
    if not ok:
        errors.append(message)


def audit_native_lanes(errors: list[str]) -> None:
    editions = load_json(ROOT / "canonical/liturgy_service_editions.json")
    require(editions.get("machine_translation_allowed") is False, "machine translation must be disabled", errors)
    require(editions.get("wrong_liturgy_fallback_allowed") is False, "wrong-rite fallback must be disabled", errors)
    require(editions.get("strict_core_scope") == STRICT_SCOPE, "edition strict-core scope mismatch", errors)
    require(editions.get("adjacent_offices_separate") is True, "adjacent offices must be separate", errors)

    libraries = {lang: service_index(lang) for lang in LANGS}
    chrys = (editions.get("editions") or {}).get("chrysostom") or {}
    require(chrys.get("displayable") is True, "Chrysostom must be the currently publishable three-language rite", errors)

    opening_markers = {
        "ar": "مباركة هي مملكة",
        "en": "Blessed is the Kingdom",
        "el": "Εὐλογημένη ἡ βασιλεία",
    }
    dismissal_markers = {
        "ar": ("المسيح إلهنا الحقيقي", "بركة الرب"),
        "en": ("May Christ our true God", "May the blessing of the Lord"),
        "el": ("Χριστὸς ὁ ἀληθινὸς Θεὸς", "Εὐλογία Κυρίου"),
    }
    foreign_patterns = {
        "ar": re.compile(r"[A-Za-z]{8,}"),
        "en": re.compile(r"[\u0600-\u06FF]{4,}"),
        "el": re.compile(r"[\u0600-\u06FF]{4,}"),
    }

    for lang in LANGS:
        service = libraries[lang].get("divine_liturgy") or {}
        require(service.get("source_language") == lang, f"Chrysostom {lang}: source_language mismatch", errors)
        review = service.get("text_integrity_review") or {}
        require(review.get("machine_translation_used") is not True, f"Chrysostom {lang}: machine translation flag", errors)
        count, chars = text_stats(service, lang)
        require(count >= 150 and chars >= 10_000, f"Chrysostom {lang}: unexpectedly short texts={count} chars={chars}", errors)
        text = lane_text(service, lang)
        require(opening_markers[lang] in text, f"Chrysostom {lang}: opening blessing missing", errors)
        require(any(marker in text for marker in dismissal_markers[lang]), f"Chrysostom {lang}: dismissal missing", errors)
        # Empty other-language fields are the lane contract. A few source names in metadata are irrelevant;
        # only prayer-text segments are checked here for obvious leakage.
        suspicious = foreign_patterns[lang].findall(text)
        if lang != "ar":
            require(not suspicious, f"Chrysostom {lang}: Arabic-script leakage in native prayer text", errors)

    basil = (editions.get("editions") or {}).get("basil") or {}
    require(basil.get("displayable") is False, "Basil must remain fail-closed", errors)
    require("OCR_CORRUPTION" in str(basil.get("ar") or ""), "Basil Arabic OCR problem must be explicit", errors)
    require("REIMPORT_REQUIRED" in str(basil.get("el") or ""), "Basil Greek re-import requirement must be explicit", errors)
    require("EXACT" in str(basil.get("en") or ""), "Basil English exact-native status missing", errors)

    pres = (editions.get("editions") or {}).get("presanctified") or {}
    require(pres.get("displayable") is False, "Presanctified must remain fail-closed", errors)
    require("EXPLANATORY_EXCERPT_NOT_FULL_SERVICE" in str(pres.get("ar") or ""), "Presanctified Arabic incompleteness must be explicit", errors)
    require("EXACT" in str(pres.get("en") or "") and "EXACT" in str(pres.get("el") or ""), "Presanctified EN/EL exact-native status missing", errors)


def audit_source_contract(errors: list[str]) -> None:
    contract = load_json(ROOT / "canonical/full_liturgy_service_contract.json")
    complete = contract.get("definition_of_complete") or {}
    require(complete.get("scope") == STRICT_SCOPE, "full contract strict scope mismatch", errors)
    require(complete.get("no_unappointed_material_allowed") is True, "unappointed material must be forbidden", errors)
    excluded = set(complete.get("excludes_as_separate_offices") or [])
    for token in ("orthros_and_matins_gospel", "hours", "proskomide", "personal_pre_communion_prayers", "thanksgiving_after_communion"):
        require(token in excluded, f"full contract missing exclusion: {token}", errors)

    data_repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    require('"STRICT_APPOINTED_LITURGY_CORE_ONLY"' in data_repo, "Android strict-core reader mode missing", errors)
    require('"APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"' in data_repo, "Android strict scope missing", errors)
    require('strictAppointedLiturgyCore' in data_repo, "Android strict-core filter missing", errors)
    require('"matins_gospel".equals(copy.optString("dynamic_slot", ""))' in data_repo, "Matins Gospel filter missing", errors)
    composer = data_repo.split("private JSONObject composeFollowAlongLiturgy", 1)[1].split("private static JSONArray strictAppointedLiturgyCore", 1)[0]
    require('findServiceInArray(library().optJSONArray("services"), "pre_communion_prayers")' not in composer, "pre-Communion prayers are still merged into Liturgy", errors)
    require("thanksgivingSegmentsForLiturgy" not in composer, "thanksgiving is still merged into Liturgy", errors)
    require("proskomide" not in composer.split("excluded_from_liturgy_core",1)[0], "Proskomide is still merged before strict exclusion metadata", errors)

    engine = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java").read_text(encoding="utf-8")
    require('"lenten_vespers_with_presanctified".equals(form)' in engine, "Presanctified service-form mapping missing", errors)
    require('if (!liturgy) service.put("extends_service_id", baseId);' in engine, "local engine still pre-wires Chrysostom fallback", errors)
    require('service.remove("extends_service_id")' in engine, "blocked local Liturgy does not remove fallback template", errors)

    updater = (ROOT / "scripts/update_liturgical_data.py").read_text(encoding="utf-8")
    require('"matins_gospel": reading_block_loc(matins_gospel' not in updater, "Matins Gospel is still injected into Divine Liturgy slot replacements", errors)
    require('"orthros_matins_gospel_belongs_to": "orthros_not_divine_liturgy"' in updater, "Orthros separation metadata missing", errors)
    require('def liturgy_day_plan(' in updater, "smart liturgy day plan missing", errors)


def audit_calendar_selection(errors: list[str]) -> None:
    u = load_updater()
    pascha = u.orthodox_pascha_gregorian(2026)
    cases = [
        (date(2026, 7, 26), "chrysostom", "morning_divine_liturgy", True),
        (pascha - timedelta(days=42), "basil", "morning_divine_liturgy", False),
        (pascha - timedelta(days=3), "basil", "vespers_with_divine_liturgy", False),
        (pascha - timedelta(days=1), "basil", "vespers_with_divine_liturgy", False),
        (date(2026, 2, 25), "presanctified", "lenten_vespers_with_presanctified", False),
        (pascha - timedelta(days=6), "presanctified", "lenten_vespers_with_presanctified", False),
        (pascha - timedelta(days=4), "presanctified", "lenten_vespers_with_presanctified", False),
        (pascha - timedelta(days=2), "no_divine_liturgy", "no_divine_liturgy", False),
        (pascha, "chrysostom", "morning_divine_liturgy", True),
    ]
    for day, expected_type, expected_form, expected_displayable in cases:
        info = u.day_info(day)
        selection = u.liturgy_service_selection(day, info)
        require(selection.get("service_type") == expected_type, f"{day}: expected {expected_type}, got {selection.get('service_type')}", errors)
        require(selection.get("service_form") == expected_form, f"{day}: expected form {expected_form}, got {selection.get('service_form')}", errors)
        require(bool(selection.get("displayable")) is expected_displayable, f"{day}: displayability mismatch", errors)
        require(selection.get("wrong_liturgy_fallback_allowed") is False, f"{day}: wrong-rite fallback enabled", errors)
        require(selection.get("full_service_scope") == STRICT_SCOPE, f"{day}: selection scope mismatch", errors)

        service = u.build_liturgy_service("divine_liturgy", day, info, [], "خدمة اليوم")
        plan = service.get("liturgy_day_plan") or {}
        require(plan.get("appointed_liturgy_type") == expected_type, f"{day}: day plan rite mismatch", errors)
        require(plan.get("strict_core_only") is True, f"{day}: day plan is not strict-core", errors)
        require(plan.get("no_unappointed_material") is True, f"{day}: day plan permits unappointed material", errors)
        if expected_displayable:
            require(service.get("full_service_complete") is True, f"{day}: publishable service not complete", errors)
            require(str(service.get("extends_service_id") or "") == str(selection.get("service_id") or ""), f"{day}: template does not match appointed rite", errors)
            slots = service.get("slot_replacements") or {}
            require("matins_gospel" not in slots, f"{day}: Matins Gospel leaked into Liturgy slots", errors)
        else:
            require("extends_service_id" not in service, f"{day}: blocked/no-Liturgy day has fallback template", errors)
            require(service.get("full_service_complete") is False, f"{day}: blocked/no-Liturgy day marked complete", errors)


def main() -> None:
    errors: list[str] = []
    audit_native_lanes(errors)
    audit_source_contract(errors)
    audit_calendar_selection(errors)
    if errors:
        for error in errors:
            print("SMART_LITURGY_ERROR", error)
        raise SystemExit(f"SMART_LITURGY_INVALID errors={len(errors)}")
    print("SMART_LITURGY_OK version=5.6.1 strict_core=true chrysostom=ar,en,el basil=blocked presanctified=blocked wrong_rite_fallback=false machine_translation=false")


if __name__ == "__main__":
    main()
