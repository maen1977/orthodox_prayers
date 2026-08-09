import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def service(pack, sid):
    return next(item for item in pack["services"] if item.get("id") == sid)


def test_arabic_office_reader_core_exists_for_all_three_problem_services():
    core = load("app/src/main/assets/data/native/arabic_office_reader_core.json")
    assert core["language"] == "ar"
    assert core["policy"] == "READER_SAFE_CORE_FAIL_CLOSED"
    by_id = {item["id"]: item for item in core["services"]}
    assert set(by_id) == {"orthros", "vespers", "small_compline"}
    minimum = {"orthros": 5, "vespers": 9, "small_compline": 4}
    for sid, expected in minimum.items():
        item = by_id[sid]
        assert item["raw_ocr_hidden_from_reader"] is True
        assert item["reader_scope"] == "READABLE_FIXED_CORE_ONLY_NOT_COMPLETE_OFFICE"
        assert len(item["segments"]) >= expected
        rendered = json.dumps(item, ensure_ascii=False)
        assert "الناهضمن" not in rendered
        assert "السوائي الكبير" not in rendered


def test_android_reader_uses_safe_core_and_preserves_daily_overlay():
    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert 'loadOptionalJsonAsset("data/native/arabic_office_reader_core.json")' in text
    assert '"ملحق اليوم الكنسي".equals(firstTitle)' in text
    assert 'safe.put("reader_safe_core", true)' in text
    assert "arabicOfficeSourceQualityNotice" not in text


def test_arabic_search_uses_readable_core_not_raw_ocr():
    index = load("app/src/main/assets/data/search/search_index_ar.json")
    docs = {item["id"]: item for item in index["documents"]}
    for sid in ("orthros", "vespers", "small_compline"):
        doc = docs[f"service:{sid}"]
        text = doc.get("display_text", "")
        assert text.strip()
        assert "الناهضمن" not in text
        assert "السوائي الكبير" not in text
        assert "النص العربي المضمّن لصلاة السَحَر موقوف" not in text


def test_optional_faithful_private_devotions_are_reader_only_and_not_collective_responses():
    payload = load("app/src/main/assets/data/native/arabic_liturgy_private_devotions.json")
    assert payload["language"] == "ar"
    assert payload["collective_response_claimed"] is False
    placements = payload["placements"]
    prayers = [p for placement in placements for p in placement["prayers"]]
    assert len(prayers) == 4
    assert {placement["event"] for placement in placements} == {"before_epistle", "great_entrance", "before_creed"}
    for prayer in prayers:
        assert prayer["delivery"] == "silent"
        assert prayer["delivery_actor"] == "faithful"
        assert prayer["not_collective_response"] is True
        assert prayer["devotional_status"] == "OPTIONAL_PRIVATE_DEVOTION_FROM_PROJECT_HISTORY"
        assert prayer["speaker"]["ar"].startswith("المؤمن في قلبه")
        assert prayer["speaker"]["en"] == "" and prayer["speaker"]["el"] == ""
        assert prayer["text"]["en"] == "" and prayer["text"]["el"] == ""


def test_exact_native_liturgy_is_unchanged_and_reader_layer_injects_devotions():
    pack = load("app/src/main/assets/data/native/library_ar.json")
    liturgy = service(pack, "divine_liturgy")
    assert not any(s.get("devotional_status") == "OPTIONAL_PRIVATE_DEVOTION_FROM_PROJECT_HISTORY" for s in liturgy["segments"])
    java = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert '"divine_liturgy".equals(id)' in java
    assert "prepareArabicLiturgyReaderDevotions" in java
    assert 'loadOptionalJsonAsset("data/native/arabic_liturgy_private_devotions.json")' in java
    assert "applyArabicLiturgyDevotionPlacement" in java
    assert '"before_section".equals(mode)' in java
    assert '"after_text_prefix".equals(mode)' in java


def test_private_devotion_anchors_exist_in_exact_arabic_liturgy():
    liturgy = service(load("app/src/main/assets/data/native/library_ar.json"), "divine_liturgy")
    segments = liturgy["segments"]
    payload = load("app/src/main/assets/data/native/arabic_liturgy_private_devotions.json")
    for placement in payload["placements"]:
        anchor = placement["anchor"]
        if placement["placement"] == "before_section":
            assert any((s.get("title") or {}).get("ar") == anchor for s in segments)
        else:
            assert any((s.get("text") or {}).get("ar", "").startswith(anchor) for s in segments)

def test_r61_does_not_claim_full_exact_arabic_offices():
    manifest = load("canonical/religious_completeness_manifest.json")
    assert manifest["languages"]["ar"]["orthros"] == "source_text_partial"
    core = load("data/services/reader/arabic_office_reader_core.json")
    for item in core["services"]:
        assert item["reader_scope"] == "READABLE_FIXED_CORE_ONLY_NOT_COMPLETE_OFFICE"
        assert item["machine_translation_added_in_r61"] is False
