from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "canonical" / "daily_liturgy_propers_inventory_2026_2050.json"
LANGS = ("ar", "en", "el")
SLOTS = ("daily_troparion", "daily_kontakion", "communion_hymn")


def load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def test_inventory_covers_every_civil_date_and_lane_without_fallback():
    data = load_inventory()
    assert data["status"] == "INVENTORY_ONLY_NOT_A_COMPLETION_CLAIM"
    assert data["completion_claim"] == "unproven_complete"
    assert data["languages"] == list(LANGS)
    assert data["slots"] == list(SLOTS)
    assert data["policy"]["same_language_source_only"] is True
    assert data["policy"]["cross_language_fallback_allowed"] is False
    assert data["policy"]["machine_translation_allowed"] is False

    expected = []
    current = date(2026, 1, 1)
    end = date(2051, 1, 1)
    while current < end:
        expected.append(current.isoformat())
        current += timedelta(days=1)
    assert [day["civil_date"] for day in data["days"]] == expected
    assert len(data["days"]) == 9131
    assert data["summary"]["civil_days"] == 9131
    assert data["summary"]["records"] == 9131 * 3 * 3

    for day in data["days"]:
        assert set(day["lanes"]) == set(LANGS)
        assert day["fail_closed"] is True
        for lang in LANGS:
            assert set(day["lanes"][lang]) == set(SLOTS)
            for slot in SLOTS:
                record = day["lanes"][lang][slot]
                assert record["status"] in {"verified", "incomplete"}
                assert record["verified"] is False
                assert record["reasons"] or record["verified"]


def test_inventory_summary_is_consistent_and_never_claims_verified_daily_coverage():
    data = load_inventory()
    eligible = [day for day in data["days"] if day["liturgy_eligible"]]
    assert len(eligible) == data["summary"]["eligible_liturgy_days"]
    assert data["summary"]["eligible_liturgy_records"] == len(eligible) * 3 * 3

    for lang in LANGS:
        for slot in SLOTS:
            key = f"{lang}:{slot}"
            summary = data["summary"]["by_language_and_slot"][key]
            eligible_records = [day["lanes"][lang][slot] for day in eligible]
            all_records = [day["lanes"][lang][slot] for day in data["days"]]
            for scope, records in (("all_civil_days", all_records), ("eligible_liturgy_days", eligible_records)):
                assert summary[scope]["text_present_days"] == sum(r["text_present"] for r in records)
                assert summary[scope]["source_registered_days"] == sum(r["source_registered"] for r in records)
                assert summary[scope]["registered_hash_days"] == sum(bool(r["registered_text_sha256"]) for r in records)
                assert summary[scope]["rights_attested_days"] == sum(r["rights_attested"] for r in records)
                assert summary[scope]["script_isolated_days"] == sum(r["script_isolated"] for r in records)
                assert summary[scope]["verified_days"] == sum(r["verified"] for r in records)
                assert summary[scope]["verified_days"] == 0


def test_inventory_texts_are_not_cross_language_when_present():
    data = load_inventory()
    for day in data["days"]:
        for lang in LANGS:
            for slot in SLOTS:
                record = day["lanes"][lang][slot]
                if record["text_present"]:
                    assert record["script_isolated"] is True, (day["civil_date"], lang, slot, record)
