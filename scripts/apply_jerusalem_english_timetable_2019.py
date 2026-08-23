"""Apply the official Jerusalem Patriarchate English 2019 timetable to the English lane."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "canonical/jerusalem_jordan_fixed_commemorations_native.json"
CORPUS_PATH = ROOT / "canonical/english_local_jerusalem_timetable_2019.json"
SOURCE_ID = "jerusalem_patriarchate_english_timetable_2019"
SOURCE_URL = "https://en.jerusalem-patriarchate.info/timetable-of-church-services-2/"
EXPECTED_SNAPSHOT_SHA256 = "e67512327d3c0bddfbb44bf642e9cbc5742cb31f49cd4595eca320caa6a81b78"


def main() -> int:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    entries = corpus.get("entries")
    if not isinstance(entries, dict) or len(entries) != 365:
        raise ValueError("official Jerusalem English corpus must contain exactly 365 entries")
    if "02-29" in entries:
        raise ValueError("non-leap 2019 English source must not invent a 02-29 row")
    if corpus.get("source_id") != SOURCE_ID or corpus.get("source_url") != SOURCE_URL:
        raise ValueError("English corpus source identity mismatch")
    if corpus.get("source_snapshot_sha256") != EXPECTED_SNAPSHOT_SHA256:
        raise ValueError("English corpus snapshot hash mismatch")
    if corpus.get("machine_translation_used") is not False:
        raise ValueError("English corpus must declare machine_translation_used=false")
    if corpus.get("cross_language_fallback") is not False:
        raise ValueError("English corpus must declare cross_language_fallback=false")

    by_slot = {row.get("old_calendar_month_day"): row for row in evidence.get("records", [])}
    if len(by_slot) != 366:
        raise ValueError("evidence must contain all 366 old-calendar slots")
    changed = 0
    for slot, text in sorted(entries.items()):
        row = by_slot.get(slot)
        if row is None:
            raise ValueError(f"English source slot missing from evidence: {slot}")
        lane = row.get("lanes", {}).get("en")
        if not isinstance(lane, dict):
            raise ValueError(f"missing English lane: {slot}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"empty English source text: {slot}")
        lane.update({
            "text": text,
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "source_year": 2019,
            "jurisdiction": "jerusalem_patriarchate",
            "evidence_status": "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE",
            "comparative": False,
            "fixed_slot_eligible": True,
            "eligibility_reason": "OFFICIAL_ENGLISH_TIMETABLE_NATIVE_TEXT",
            "source_endpoint": SOURCE_URL,
        })
        changed += 1

    leap = by_slot["02-29"]["lanes"]["en"]
    if leap.get("source_id") != "holy_trinity_calendar_en_comparative":
        raise ValueError("02-29 must remain the existing comparative English record")
    if leap.get("comparative") is not True or leap.get("jurisdiction") != "comparative_not_jerusalem_jordan":
        raise ValueError("02-29 comparative English provenance was changed unexpectedly")

    artifacts = evidence.setdefault("source_artifacts", [])
    artifact = {
        "source_id": SOURCE_ID,
        "language": "en",
        "source_year": 2019,
        "jurisdiction": "jerusalem_patriarchate",
        "source_url": SOURCE_URL,
        "artifact_sha256": EXPECTED_SNAPSHOT_SHA256,
        "artifact_available_at_build_time": True,
        "promotion": "365_slots_verified_from_official_english_timetable",
        "notes": (
            "Official Jerusalem Patriarchate English timetable page. Native English daily rows were extracted "
            "from January–December 2019 old-calendar tables; 02-29 is not present because 2019 is non-leap "
            "and remains comparative until an official local English leap-day record is found."
        ),
    }
    existing = next((item for item in artifacts if item.get("source_id") == SOURCE_ID), None)
    if existing is None:
        artifacts.append(artifact)
    elif existing != artifact:
        raise ValueError("English source artifact metadata drifted")

    coverage = evidence.setdefault("coverage", {})
    coverage["en_local_english_timetable_2019_slots"] = changed
    coverage["en_local_english_timetable_2019_pending_slots"] = 1
    coverage["en_comparative_records"] = 1
    coverage["strict_named_local_gate"] = False
    coverage["strict_gate_note"] = (
        "Arabic and Greek local lanes are source-backed. English has 365 official Jerusalem local timetable "
        "slots; 02-29 remains comparative because no official local English leap-day text has been identified. "
        "The strict three-language gate remains false."
    )
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"promoted_english_local_slots": changed, "english_comparative_slots": 1, "strict_named_local_gate": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
