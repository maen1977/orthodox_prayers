"""Update the Jerusalem/Jordan acquisition queue from native-evidence coverage."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "canonical" / "jordan_jerusalem_commemoration_acquisition_queue.json"
EVIDENCE = ROOT / "canonical" / "jerusalem_jordan_fixed_commemorations_native.json"


def is_verified_local(language: str, entry: dict) -> bool:
    expected = {
        "ar": "VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE",
        "en": "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE",
        "el": "VERIFIED_NATIVE_LOCAL_GREEK_SOURCE",
    }[language]
    return (
        entry.get("evidence_status") == expected
        and entry.get("jurisdiction") in {"jerusalem_patriarchate", "jerusalem_jordan"}
        and entry.get("comparative") is False
        and entry.get("fixed_slot_eligible") is True
    )


def main() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    by_slot = {
        row["old_calendar_month_day"]: row
        for row in evidence.get("records", [])
        if isinstance(row, dict) and row.get("old_calendar_month_day")
    }
    language_summary = {}
    for language in ("ar", "en", "el"):
        entries = [
            (row.get("lanes") or {}).get(language)
            for row in by_slot.values()
            if isinstance((row.get("lanes") or {}).get(language), dict)
        ]
        language_summary[language] = {
            "slots_with_evidence": len(entries),
            "verified_local_slots": sum(is_verified_local(language, entry) for entry in entries),
            "visual_review_or_pending_slots": sum("REQUIRES_VISUAL_REVIEW" in str(entry.get("evidence_status") or "") for entry in entries),
            "comparative_slots": sum(bool(entry.get("comparative")) for entry in entries),
            "source_ids": sorted({str(entry.get("source_id") or "") for entry in entries}),
        }
    strict_slots = 0
    partial_slots = 0
    for slot in queue.get("slots", []):
        key = slot.get("old_calendar_month_day")
        record = by_slot.get(key, {})
        lanes = record.get("lanes") if isinstance(record.get("lanes"), dict) else {}
        progress = {}
        for language in ("ar", "en", "el"):
            entry = lanes.get(language)
            if not isinstance(entry, dict):
                progress[language] = {"status": "MISSING_NATIVE_EVIDENCE"}
                continue
            status = str(entry.get("evidence_status") or "")
            progress[language] = {
                "status": status,
                "source_id": entry.get("source_id"),
                "source_year": entry.get("source_year"),
                "comparative": bool(entry.get("comparative")),
                "fixed_slot_eligible": bool(entry.get("fixed_slot_eligible")),
                "eligibility_reason": entry.get("eligibility_reason", ""),
            }
        all_verified = all(
            progress[language].get("status", "").startswith("VERIFIED_NATIVE_LOCAL_")
            and not progress[language].get("comparative")
            and progress[language].get("fixed_slot_eligible") is True
            for language in ("ar", "en", "el")
        )
        has_any = any(progress[language].get("status") != "MISSING_NATIVE_EVIDENCE" for language in ("ar", "en", "el"))
        if all_verified:
            strict_slots += 1
            slot["status"] = "VERIFIED_NATIVE_AR_EN_EL_LOCAL"
        elif has_any:
            partial_slots += 1
            slot["status"] = "PARTIAL_NATIVE_EVIDENCE_PENDING_PROMOTION"
        slot["native_evidence_progress"] = progress
        slot["promotion_gate"] = "CLOSED_UNTIL_VERIFIED_LOCAL_AR_EN_EL"
    queue["native_evidence_summary"] = {
        "evidence_file": "canonical/jerusalem_jordan_fixed_commemorations_native.json",
        "allowed_old_calendar_slots": 366,
        "languages": language_summary,
        "partial_evidence_slots": partial_slots,
        "strict_local_three_language_slots": strict_slots,
        "strict_named_local_gate": False,
        "comparative_english_never_counts_as_local": True,
        "machine_translation_used": False,
        "cross_language_fallback": False,
    }
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(queue["native_evidence_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
