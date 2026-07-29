#!/usr/bin/env python3
"""Build a complete unsigned daily candidate without touching signed app data.

The calendar fixture determines the appointed references. Exact same-language
Bible wording is resolved from checked-in registered native corpora. The output
is intentionally kept outside ``data/calendar/today.json`` until the protected
release signer signs and promotes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from native_text_contract import ROOT, LANGUAGES, load_contract
import enforce_native_daily_lanes as lanes
import fill_daily_from_native_corpora as fill
import orthodox_integrity as integrity
import update_liturgical_data as update


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def release_policy_baseline() -> dict[str, Any]:
    """Load schema-locked policy fields from the last verified signed release.

    Candidate state belongs in candidate_metadata and signature_state. The
    schema-level integrity/publication values describe the enforced policy and
    must remain identical before and after the detached signature is added.
    """
    path = ROOT / "data" / "calendar" / "today.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    return {
        "language_content_mode": baseline["language_content_mode"],
        "language_sources": baseline["language_sources"],
        "integrity": baseline["integrity"],
        "publication": baseline["publication"],
    }


def reference_evidence(day: str, epistle: str, gospel: str) -> dict[str, Any]:
    record = {
        "date_iso": day,
        "epistle_reference": epistle,
        "gospel_reference": gospel,
        "authority": "Orthodox Church in America daily lectionary",
        "url": f"https://www.oca.org/readings/daily/{day.replace('-', '/')}",
    }
    return {
        "id": "orthodox_church_in_america",
        "priority": 5,
        "official": True,
        "url": record["url"],
        "status": "current",
        "date_iso": day,
        "epistle_reference": epistle,
        "gospel_reference": gospel,
        "tone": None,
        "prokeimenon_text": None,
        "sha256": hashlib.sha256(canonical_bytes(record)).hexdigest(),
        "reason": "Official Orthodox lectionary authority for the appointed references; Bible text is supplied independently by registered same-language public-domain corpora.",
    }


def build(day_text: str, output: Path) -> dict[str, Any]:
    day = datetime.strptime(day_text, "%Y-%m-%d").date()
    data = update.build_day(day)
    policy = release_policy_baseline()
    data["language_content_mode"] = policy["language_content_mode"]
    data["language_sources"] = policy["language_sources"]
    scripture = [r for r in data.get("readings", []) if r.get("kind") in {"epistle", "gospel"}]
    if len(scripture) != 2:
        raise RuntimeError("daily fixture must resolve exactly one epistle and one gospel")
    epistle = next(r for r in scripture if r["kind"] == "epistle")
    gospel = next(r for r in scripture if r["kind"] == "gospel")
    ep_ref = str(epistle.get("reference", {}).get("en") or "")
    go_ref = str(gospel.get("reference", {}).get("en") or "")
    data["source_evidence"] = [reference_evidence(day_text, ep_ref, go_ref)]
    data["schema_version"] = max(9, int(data.get("schema_version") or 0))
    data["machine_translation_used"] = False
    data["automatic_diacritization_used"] = False
    data["translation_fallback_policy"] = "DISABLED_NO_CROSS_LANGUAGE_FALLBACK"
    data["native_text_contract"] = "canonical/source_native_contract.json"
    data["lectionary_reference_authority"] = {
        "source_id": "oca_official_english",
        "official": True,
        "date_iso": day_text,
        "epistle_reference": ep_ref,
        "gospel_reference": go_ref,
        "text_reuse": False,
        "role": "APPOINTED_REFERENCE_ONLY",
    }
    data["publication"] = dict(policy["publication"])
    data["publication"].update({
        "selected_source": "orthodox_church_in_america",
        "signature_required_before_promotion": True,
        "candidate_state": "COMPLETE_UNSIGNED_CANDIDATE_AWAITING_PROTECTED_SIGNATURE",
    })
    data["integrity"] = dict(policy["integrity"])
    data["integrity"].update({
        "signature_state": "PENDING_PROTECTED_RELEASE_SIGNER",
        "automatic_diacritization_used": False,
        "candidate_source_status": "VERIFIED_OFFICIAL_REFERENCES_AND_EXACT_NATIVE_CORPORA_UNSIGNED",
    })

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fill.process(output)

    data = json.loads(output.read_text(encoding="utf-8"))
    contract = load_contract()
    target_date = str(data["date_iso"])
    for readings in lanes.reading_lists(data):
        for reading in readings:
            if isinstance(reading, dict):
                lanes.enforce_reading(reading, data, target_date, contract)

    today_readings = data.get("readings") or []
    next_readings = data.get("integrity_inputs", {}).get("next_sunday", {}).get("readings") or []
    integrity.rebuild_services(data, today_readings, next_readings)

    # Reassert candidate-level state after helper functions rebuild dynamic data.
    data["schema_version"] = max(9, int(data.get("schema_version") or 0))
    data["language_content_mode"] = policy["language_content_mode"]
    data["language_sources"] = policy["language_sources"]
    data["publication"].update({
        "status": "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED",
        "candidate_state": "COMPLETE_UNSIGNED_CANDIDATE_AWAITING_PROTECTED_SIGNATURE",
        "signature_required_before_promotion": True,
    })
    data["integrity"].update({
        "status": "VERIFIED_OFFICIAL_SOURCES",
        "ai_scripture_translation_used": False,
        "ai_liturgical_translation_used": False,
        "signature_state": "PENDING_PROTECTED_RELEASE_SIGNER",
        "candidate_source_status": "VERIFIED_OFFICIAL_REFERENCES_AND_EXACT_NATIVE_CORPORA_UNSIGNED",
    })
    data["candidate_metadata"] = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "builder": "scripts/build_release_candidate.py",
        "protected_promotion_target": "data/calendar/today.json and app/src/main/assets/data/today.json",
        "must_not_ship_unsigned": True,
        "languages": list(LANGUAGES),
    }
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Built complete unsigned daily candidate: {output.relative_to(ROOT)}")
    print(f"sha256={digest}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="civil date in YYYY-MM-DD")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (ROOT / "data" / "calendar" / "candidates" / f"{args.date}.json")
    if not output.is_absolute():
        output = ROOT / output
    build(args.date, output)


if __name__ == "__main__":
    main()
