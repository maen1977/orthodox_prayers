import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
REQUIRED_CHURCH_IDS = {
    "church_baptism",
    "church_eucharist",
    "church_confession",
    "church_betrothal",
    "church_marriage",
    "church_crowns_removal",
    "church_unction",
    "church_funeral",
    "church_memorial",
    "church_home_blessing",
    "church_priesthood",
    "church_great_water",
    "church_hours",
}


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def service(pack, service_id):
    return next(item for item in pack["services"] if item.get("id") == service_id)


def test_church_service_catalog_has_thirteen_native_cards_per_language():
    catalog = load_json("canonical/church_service_catalog.json")
    assert catalog["policy"] == "PINNED_NATIVE_CHURCH_SERVICE_CATALOG_OVERLAID_BY_BUILD_GENERATED_FULL_TEXT"
    for lang in LANGS:
        cards = catalog["languages"][lang]["services"]
        assert {item["id"] for item in cards} == REQUIRED_CHURCH_IDS
        assert all(item.get("category") == "church_service" for item in cards)
        assert all(item.get("source_language") == lang for item in cards)


def test_native_libraries_keep_church_service_hub_offline():
    for lang in LANGS:
        pack = load_json(f"app/src/main/assets/data/native/library_{lang}.json")
        cards = [item for item in pack["services"] if item.get("category") == "church_service"]
        assert {item["id"] for item in cards} == REQUIRED_CHURCH_IDS
        assert all(item.get("catalog_snapshot") is True for item in cards)
        assert all(item.get("catalog_snapshot_policy") == "BUILD_GENERATED_NATIVE_TEXT_OVERLAY_IF_AVAILABLE" for item in cards)


def test_native_pack_builder_cannot_drop_church_service_catalog_again():
    text = (ROOT / "scripts/build_native_service_packs.py").read_text(encoding="utf-8")
    assert "CHURCH_SERVICE_CATALOG" in text
    assert "catalog_snapshot_policy" in text
    assert "BUILD_GENERATED_NATIVE_TEXT_OVERLAY_IF_AVAILABLE" in text
    assert "pack[\"services\"].append(service)" in text


def test_arabic_liturgy_marks_existing_faithful_private_prayers_with_event_context():
    pack = load_json("app/src/main/assets/data/native/library_ar.json")
    liturgy = service(pack, "divine_liturgy")
    faithful = [segment for segment in liturgy["segments"] if segment.get("delivery_actor") == "faithful"]
    assert len(faithful) >= 5
    contexts = {(segment.get("event_context") or {}).get("ar", "") for segment in faithful}
    assert "أثناء الدخول الصغير — صلاة المؤمن بهدوء" in contexts
    assert "بعد تلاوة الإنجيل — صلاة المؤمن بهدوء" in contexts
    assert "أثناء الدورة الكبرى وحمل القرابين — صلاة المؤمن بهدوء" in contexts
    assert "أثناء تذكارات الأنافورا — صلاة المؤمن بهدوء" in contexts
    assert "قبل المناولة المقدسة — تُقال سرًا" in contexts
    great_entrance = next(
        segment for segment in faithful
        if (segment.get("text") or {}).get("ar", "").startswith("لنطرح الآن كل اهتمام دنيوي")
    )
    assert great_entrance["delivery"] == "silent"
    assert great_entrance["event_context"]["editorial_metadata_only"] is True


def test_english_and_greek_communion_private_prayers_have_native_lane_context_only():
    expectations = {
        "en": "Before Holy Communion — said privately",
        "el": "Πρὸ τῆς Θείας Μεταλήψεως — λέγεται κατ’ ἰδίαν",
    }
    for lang, expected in expectations.items():
        pack = load_json(f"app/src/main/assets/data/native/library_{lang}.json")
        liturgy = service(pack, "divine_liturgy")
        faithful = [segment for segment in liturgy["segments"] if segment.get("delivery_actor") == "faithful"]
        assert faithful
        assert any((segment.get("event_context") or {}).get(lang) == expected for segment in faithful)
        for segment in faithful:
            context = segment.get("event_context")
            if not context:
                continue
            for other in set(LANGS) - {lang}:
                assert context.get(other, "") == ""


def test_reader_renders_event_context_without_changing_prayer_text():
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/ReaderAdapter.java").read_text(encoding="utf-8")
    assert "addEventContextBadge(card, segment);" in text
    assert 'segment.optJSONObject("event_context")' in text
    assert "ui.infoBadge(context)" in text
    # The source text still comes from the normal localized text object.
    assert 'data.localizedValue(segment.optJSONObject("text"), "")' in text


def test_arabic_office_reader_uses_source_boundaries_not_text_rewriting():
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "prepareOfficeReaderView" in text
    assert 'text.contains("صلوة الغروب")' in text
    assert 'text.contains("صلوة النور") && text.contains("الصغرى")' in text
    assert "isArabicOfficeRunningHeader" in text
    assert "reader_boundary_cleanup" in text
    assert "لم يضف التطبيق بقية الصلاة بالتخمين أو الترجمة الآلية" in text


def test_arabic_orthros_source_remains_fail_closed_and_is_not_ai_corrected():
    pack = load_json("app/src/main/assets/data/native/library_ar.json")
    orthros = service(pack, "orthros")
    assert orthros.get("displayable") is False
    assert orthros.get("publication_status") == "BLOCKED_ARABIC_OCR_REIMPORT_REQUIRED"
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "arabicOfficeSourceQualityNotice" in text
    assert "لم يستخدم ترجمة آلية أو تصحيحًا بالذكاء الاصطناعي" in text


def test_arabic_vespers_and_small_compline_source_boundaries_are_detectable():
    pack = load_json("app/src/main/assets/data/native/library_ar.json")
    vespers = service(pack, "vespers")["segments"]
    small = service(pack, "small_compline")["segments"]
    vespers_index = next(i for i, segment in enumerate(vespers) if "صلوة الغروب" in (segment.get("text") or {}).get("ar", ""))
    small_index = next(i for i, segment in enumerate(small) if "صلوة النور" in (segment.get("text") or {}).get("ar", "") and "الصغرى" in (segment.get("text") or {}).get("ar", ""))
    assert vespers_index > 0
    assert small_index > 0


def test_no_machine_translation_is_introduced_by_r60_catalog():
    catalog = load_json("canonical/church_service_catalog.json")

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "machine_translation_used":
                    assert child is not True
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(catalog)


def test_release_gate_covers_r60_and_church_service_regression():
    text = (ROOT / "scripts/run_local_daily_release_gate.py").read_text(encoding="utf-8")
    assert "tests/test_r60_final_service_reader_polish.py" in text
    assert "tests/test_v540_church_service_section.py" in text
