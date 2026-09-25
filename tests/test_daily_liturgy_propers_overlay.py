from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "canonical" / "daily_liturgy_propers_overlay.json"
LANGS = ("ar", "en", "el")
SLOTS = {"daily_troparion", "daily_kontakion", "communion_hymn"}
ATTESTATION = "USER_CONFIRMED_REPUBLICATION_PERMISSION_FOR_ORTHODOX_DAILY_PROPERS_SOURCES_2026_08_24"


def load_overlay() -> dict:
    return json.loads(OVERLAY.read_text(encoding="utf-8"))


def test_partial_beheading_entry_is_native_and_fail_closed():
    payload = load_overlay()
    entry = payload["entries"]["2026-09-11"]

    assert entry["julian_date"] == "2026-08-29"
    assert entry["proper_id"] == "beheading_forerunner_john"
    assert entry["verified_slots"] == ["daily_kontakion", "daily_troparion"]
    assert entry["complete_three_slot_entry"] is False
    assert set(entry["languages"]) == set(LANGS)

    expected_sources = {
        "ar": "https://www.antiochpatriarchate.org/ar/page/713/",
        "en": "https://www.goarch.org/-/commemoration-of-the-beheading-of-the-holy-and-glorious-prophet-forerunner-and-baptist-john",
        "el": "https://digitalchantstand.goarch.org/goa/dcs/p/s/2026/08/29/ma3/gr-en/index.html",
    }
    for language in LANGS:
        lane = entry["languages"][language]
        assert set(lane) == {"daily_troparion", "daily_kontakion"}
        assert "communion_hymn" not in lane
        for slot, item in lane.items():
            text = item["text"].strip()
            assert text
            assert item["text_sha256"] == sha256(text.encode("utf-8")).hexdigest()
            assert item["source_url"] == expected_sources[language]
            assert item["permission_confirmed"] is True
            assert item["redistribution_review_required"] is False
            assert item["authorization_reference"] == ATTESTATION
            assert item["machine_translation_used"] is False
            assert item["ai_translation_used"] is False
            assert item["automatic_diacritization_used"] is False
            assert item["script_isolated"] is True
        if language in {"ar", "el"}:
            assert re.search(r"[A-Za-z]", lane["daily_troparion"]["text"]) is None
            assert re.search(r"[A-Za-z]", lane["daily_kontakion"]["text"]) is None


def test_partial_entry_does_not_relax_three_language_slot_alignment():
    payload = load_overlay()
    for entry in payload["entries"].values():
        slot_sets = [set(entry["languages"][language]) for language in LANGS]
        assert slot_sets[0] == slot_sets[1] == slot_sets[2]
        assert slot_sets[0]
        assert slot_sets[0].issubset(SLOTS)
        assert entry["complete_three_slot_entry"] is (slot_sets[0] == SLOTS)


def test_euthymius_partial_entry_is_mapped_to_julian_january_20():
    payload = load_overlay()
    entry = payload["entries"]["2026-02-02"]

    assert entry["julian_date"] == "2026-01-20"
    assert entry["proper_id"] == "euthymius_the_great"
    assert entry["verified_slots"] == ["daily_kontakion", "daily_troparion"]
    assert entry["complete_three_slot_entry"] is False

    expected_sources = {
        "ar": "https://www.antiochpatriarchate.org/ar/page/1596/",
        "en": "https://www.goarch.org/chapel/saints?contentid=395&PCode=14LM&D=M&DT=01/20/2025&language=en",
        "el": "https://www.goarch.org/chapel/saints?contentid=395&PCode=14LM&D=M&DT=01/20/2025&language=el",
    }
    for language in LANGS:
        lane = entry["languages"][language]
        assert set(lane) == {"daily_troparion", "daily_kontakion"}
        assert "communion_hymn" not in lane
        for slot, item in lane.items():
            text = item["text"].strip()
            assert text
            assert item["text_sha256"] == sha256(text.encode("utf-8")).hexdigest()
            assert item["source_url"] == expected_sources[language]
            assert item["permission_confirmed"] is True
            assert item["redistribution_review_required"] is False
            assert item["authorization_reference"] == ATTESTATION
            assert item["machine_translation_used"] is False
            assert item["ai_translation_used"] is False
            assert item["automatic_diacritization_used"] is False
            assert item["script_isolated"] is True
        if language in {"ar", "el"}:
            assert re.search(r"[A-Za-z]", lane["daily_troparion"]["text"]) is None
            assert re.search(r"[A-Za-z]", lane["daily_kontakion"]["text"]) is None
