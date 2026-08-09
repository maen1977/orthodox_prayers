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


def test_arabic_office_reader_hides_raw_ocr_and_uses_readable_core():
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "prepareOfficeReaderView" in text
    assert "arabicOfficeReadableCore" in text
    assert "arabic_office_reader_core.json" in text
    assert 'safe.put("raw_ocr_hidden_from_reader", true)' in text

def test_arabic_orthros_raw_source_remains_blocked_but_reader_has_safe_core():
    pack = load_json("app/src/main/assets/data/native/library_ar.json")
    orthros = service(pack, "orthros")
    assert orthros.get("displayable") is False
    assert orthros.get("publication_status") == "BLOCKED_ARABIC_OCR_REIMPORT_REQUIRED"
    core = load_json("app/src/main/assets/data/native/arabic_office_reader_core.json")
    safe = service(core, "orthros")
    assert safe.get("raw_ocr_hidden_from_reader") is True
    assert len(safe.get("segments", [])) >= 5
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "arabicOfficeReadableCore" in text
    assert "لم يستخدم ترجمة آلية أو تصحيحًا بالذكاء الاصطناعي" not in text

def test_arabic_vespers_and_small_compline_have_readable_reader_cores():
    core = load_json("app/src/main/assets/data/native/arabic_office_reader_core.json")
    vespers = service(core, "vespers")
    small = service(core, "small_compline")
    assert vespers.get("raw_ocr_hidden_from_reader") is True
    assert small.get("raw_ocr_hidden_from_reader") is True
    assert len(vespers.get("segments", [])) >= 9
    assert len(small.get("segments", [])) >= 4

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
