import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
EXPECTED_IDS = [
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
]


def _library(lang):
    p = ROOT / f"app/src/main/assets/data/native/library_{lang}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _church(lang):
    return [s for s in _library(lang)["services"] if s.get("category") == "church_service"]


def _refs(service):
    return [s["canonical_reference"] for s in service.get("segments", []) if s.get("canonical_reference")]


def _service(lang, service_id):
    return next(s for s in _church(lang) if s["id"] == service_id)


def test_prayer_hub_exposes_church_service_category():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/PrayerHubScreen.java").read_text(encoding="utf-8")
    assert 'addCategory(page, "church_service", local(com.orthodoxprayers.privateapp.R.string.ui_church_service_section));' in source


def test_church_service_title_is_localized_in_all_ui_lanes():
    expected = {
        "ar": "خدمة كنسية",
        "en": "Church Service",
        "el": "Ἐκκλησιαστικὴ Ἀκολουθία",
    }
    paths = {
        "ar": ROOT / "app/src/main/res/values/ui_strings.xml",
        "en": ROOT / "app/src/main/res/values-en/ui_strings.xml",
        "el": ROOT / "app/src/main/res/values-el/ui_strings.xml",
    }
    for lang, path in paths.items():
        text = path.read_text(encoding="utf-8")
        assert f'<string name="ui_church_service_section">{expected[lang]}</string>' in text


def test_all_three_lanes_have_same_church_service_catalog():
    for lang in LANGS:
        assert [s["id"] for s in _church(lang)] == EXPECTED_IDS


def test_each_service_contains_only_its_native_visible_lane():
    visible_fields = ("title", "summary")
    for lang in LANGS:
        for service in _church(lang):
            assert service["source_language"] == lang
            for field in visible_fields:
                value = service[field]
                assert value[lang].strip()
                for other in LANGS:
                    if other != lang:
                        assert value.get(other, "") == ""
            for segment in service.get("segments", []):
                for field in ("title", "text", "speaker"):
                    if field not in segment or not isinstance(segment[field], dict):
                        continue
                    if any(segment[field].values()):
                        assert segment[field].get(lang, "").strip()
                        for other in LANGS:
                            if other != lang:
                                assert segment[field].get(other, "") == ""
            assert service["native_source"].get("machine_translation_used") is False


def test_fixed_readings_match_verified_rite_contract():
    expected = {
        "church_baptism": ["ROM.6.3-12", "MAT.28.16-20"],
        "church_marriage": ["PSA.128.1-6", "EPH.5.20-33", "JHN.2.1-11"],
        "church_funeral": ["PSA.91.1-16", "1TH.4.13-17", "JHN.5.24-30"],
        "church_great_water": ["ISA.35.1-10", "ISA.55.1-13", "ISA.12.3-6", "1CO.10.1-4", "MRK.1.9-11"],
    }
    for lang in LANGS:
        for service_id, refs in expected.items():
            assert _refs(_service(lang, service_id)) == refs


def test_holy_unction_contains_seven_epistles_and_seven_gospels():
    expected = [
        "JAS.5.10-16", "LUK.10.25-37",
        "ROM.15.1-7", "LUK.19.1-10",
        "1CO.12.27-31;1CO.13.1-8", "MAT.10.1;MAT.10.5-8",
        "2CO.6.16-18;2CO.7.1", "MAT.8.14-23",
        "2CO.1.8-11", "MAT.25.1-13",
        "GAL.5.22-26;GAL.6.1-2", "MAT.15.21-28",
        "1TH.5.14-23", "MAT.9.9-13",
    ]
    for lang in LANGS:
        assert _refs(_service(lang, "church_unction")) == expected


def test_hours_card_links_to_existing_four_hours_without_duplication():
    expected = ["first_hour", "third_hour", "sixth_hour", "ninth_hour"]
    for lang in LANGS:
        related = _service(lang, "church_hours").get("related_services", [])
        assert [item["service_id"] for item in related] == expected
        for item in related:
            assert item["label"][lang].strip()
            assert all(not item["label"].get(other, "") for other in LANGS if other != lang)


def test_eucharist_card_routes_to_existing_liturgy_and_communion_prayers():
    expected = ["divine_liturgy", "pre_communion_prayers", "thanksgiving_after_communion"]
    for lang in LANGS:
        related = _service(lang, "church_eucharist").get("related_services", [])
        assert [item["service_id"] for item in related] == expected


def test_church_scripture_is_resolved_only_from_bundled_bible_repository():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    block = source[source.index("private void resolveChurchServiceScripture"):source.index("private static void appendDailyLiturgyOverlay")]
    assert "BibleCorpusRepository" in source
    assert "bibleCorpusRepository.resolve(language, reference)" in block
    assert "HttpURLConnection" not in block
    assert "URL(" not in block


def test_arabic_gospel_labels_use_full_gospel_names():
    content = json.dumps(_church("ar"), ensure_ascii=False)
    for name in ("إنجيل متى", "إنجيل مرقس", "إنجيل لوقا", "إنجيل يوحنا"):
        assert name in content
    # Do not regress to bare Gospel-book labels in the newly added reading labels.
    assert not re.search(r'الإنجيل[^\n\"]*—\s*(?:متى|مرقس|لوقا|يوحنا)\s', content)


def test_greek_visible_church_content_has_no_arabic_or_english_ui_leakage():
    # Source URLs/metadata are not rendered service content; check title/summary/segments only.
    latin_word = re.compile(r"\b(?:public|domain|corpus|Church|Service|Gospel|Epistle)\b", re.I)
    arabic = re.compile(r"[\u0600-\u06FF]")
    for service in _church("el"):
        visible = [service["title"]["el"], service["summary"]["el"]]
        for segment in service.get("segments", []):
            for field in ("title", "text", "speaker"):
                if isinstance(segment.get(field), dict):
                    visible.append(segment[field].get("el", ""))
        joined = "\n".join(visible)
        assert not arabic.search(joined)
        assert not latin_word.search(joined)


def test_canonical_and_apk_native_service_libraries_stay_identical():
    for lang in LANGS:
        apk = ROOT / f"app/src/main/assets/data/native/library_{lang}.json"
        canonical = ROOT / f"data/services/native/library_{lang}.json"
        assert apk.read_bytes() == canonical.read_bytes()
