"""Apply only manually reviewed Arabic source-crop transcriptions to native evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "canonical/jerusalem_jordan_fixed_commemorations_native.json"
DEFAULT_PACKET = ROOT / "canonical/arabic_visual_review_promotions.json"


def apply(evidence: dict, packet: dict) -> tuple[dict, dict]:
    if packet.get("machine_translation_used") is not False:
        raise ValueError("Arabic promotion packet must declare machine_translation_used=false")
    if packet.get("cross_language_fallback") is not False:
        raise ValueError("Arabic promotion packet must declare cross_language_fallback=false")
    source_id = packet.get("source_id")
    source_url = packet.get("source_url")
    if not source_id or not source_url:
        raise ValueError("Arabic promotion packet must declare source_id and source_url")
    records = evidence.get("records")
    promotions = packet.get("records")
    if not isinstance(records, list) or not isinstance(promotions, dict):
        raise ValueError("evidence records and promotion records must be present")
    by_slot = {row.get("old_calendar_month_day"): row for row in records}
    missing = sorted(set(promotions) - set(by_slot))
    if missing:
        raise ValueError("promotion slots missing from evidence: " + ", ".join(missing))
    changed = 0
    for slot, text in promotions.items():
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{slot}: promoted Arabic text must be non-empty")
        row = by_slot[slot]
        lanes = row.setdefault("lanes", {})
        lane = lanes.setdefault("ar", {})
        if lane.get("source_id") != source_id or lane.get("source_url") != source_url:
            raise ValueError(f"{slot}/ar: packet source does not match evidence source")
        lane["text"] = text.strip()
        lane["evidence_status"] = "VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE"
        lane["comparative"] = False
        lane["fixed_slot_eligible"] = True
        lane["eligibility_reason"] = "VISUALLY_REVIEWED_SOURCE_PAGE_CROP"
        changed += 1
    evidence["coverage"]["strict_named_local_gate"] = False
    evidence["coverage"]["arabic_visual_review_promoted_slots"] = changed
    evidence["coverage"]["arabic_visual_review_pending_slots"] = len(records) - changed
    evidence["coverage"]["strict_gate_note"] = (
        "Arabic promotions are local and visually reviewed; the strict three-language gate remains false "
        "because the English lane is comparative rather than Jerusalem/Jordan local."
    )
    summary = {
        "promoted_arabic_slots": changed,
        "pending_arabic_slots": len(records) - changed,
        "excluded_pending_slots": packet.get("excluded_pending_slots", []),
        "strict_named_local_gate": evidence["coverage"]["strict_named_local_gate"],
    }
    return evidence, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    updated, summary = apply(evidence, packet)
    args.evidence.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
