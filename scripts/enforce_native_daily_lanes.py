#!/usr/bin/env python3
"""Enforce same-language official-source provenance on daily religious text.

This script never translates or fills missing content. It removes legacy/cross-lane
religious text and marks it unavailable until an approved official native source
is imported. Interface labels and explanatory status messages remain localized.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, source_url_allowed

SCRIPTURE_KINDS = {"epistle", "gospel", "prokeimenon"}
EXACT_STATUSES = {"VERIFIED_EXACT_NATIVE_SOURCE", "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS"}


def reading_lists(data: dict[str, Any]) -> Iterable[list[Any]]:
    if isinstance(data.get("readings"), list):
        yield data["readings"]
    sunday = data.get("next_sunday")
    if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
        yield sunday["readings"]
    integrity_inputs = data.get("integrity_inputs")
    if isinstance(integrity_inputs, dict):
        sunday = integrity_inputs.get("next_sunday")
        if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
            yield sunday["readings"]
    for service in data.get("services") or []:
        if isinstance(service, dict) and isinstance(service.get("readings"), list):
            yield service["readings"]


def date_evidence(data: dict[str, Any], target_date: str, language: str, contract: dict[str, Any]) -> dict[str, Any] | None:
    allowed = contract["language_lanes"][language]["priority"]
    candidates = []
    for evidence in data.get("source_evidence") or []:
        if not isinstance(evidence, dict):
            continue
        if evidence.get("date_iso") != target_date or evidence.get("status") != "current":
            continue
        source_id = str(evidence.get("id") or "")
        aliases = {
            "ar": {
                "orthodox_jordan": "orthodox_jordan",
                "antioch_patriarchate": "antioch_patriarchate_ar",
            },
            "en": {
                "official_greek_orthodox": "goarch_online_chapel",
                "orthodox_church_in_america": "oca_official_english",
                "jerusalem_patriarchate": "jerusalem_patriarchate_en",
            },
            "el": {},
        }
        normalized = aliases.get(language, {}).get(source_id, source_id)
        if normalized not in allowed:
            continue
        url = str(evidence.get("url") or "")
        if not source_url_allowed(normalized, url, contract):
            continue
        candidates.append((allowed.index(normalized), normalized, evidence))
    if not candidates:
        return None
    _, normalized, evidence = sorted(candidates, key=lambda item: item[0])[0]
    return {"source_id": normalized, "evidence": evidence}


def existing_exact_evidence(reading: dict[str, Any], language: str, contract: dict[str, Any]) -> dict[str, Any] | None:
    native = reading.get("native_source_verification")
    item = native.get(language) if isinstance(native, dict) else None
    if not isinstance(item, dict):
        return None
    source_id = str(item.get("source_id") or "")
    if item.get("status") not in EXACT_STATUSES or item.get("ai_translation_used") is not False:
        return None
    if not source_allowed(language, source_id, contract):
        return None
    return item


def unavailable(language: str, canonical_reference: str) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE_UNTIL_EXACT_OFFICIAL_NATIVE_SOURCE",
        "source_id": None,
        "canonical_reference": canonical_reference,
        "reference_available": False,
        "text_available": False,
        "ai_translation_used": False,
        "automatic_diacritization_used": False,
        "reason": "same_language_official_source_not_available",
    }


def canonical_reference(reading: dict[str, Any]) -> str:
    integrity = reading.get("integrity")
    if isinstance(integrity, dict) and integrity.get("canonical_reference"):
        return str(integrity["canonical_reference"])
    for evidence in (reading.get("translation_verification") or {}).values() if isinstance(reading.get("translation_verification"), dict) else []:
        if isinstance(evidence, dict) and evidence.get("canonical_reference"):
            return str(evidence["canonical_reference"])
    return ""


def enforce_reading(reading: dict[str, Any], data: dict[str, Any], target_date: str, contract: dict[str, Any]) -> None:
    kind = str(reading.get("kind") or "")
    if kind not in SCRIPTURE_KINDS:
        return
    reference = reading.get("reference") if isinstance(reading.get("reference"), dict) else {}
    body = reading.get("body") if isinstance(reading.get("body"), dict) else {}
    source = reading.get("source") if isinstance(reading.get("source"), dict) else {}
    canonical = canonical_reference(reading)
    native_verification: dict[str, Any] = {}

    for language in LANGUAGES:
        exact = existing_exact_evidence(reading, language, contract)
        daily = date_evidence(data, target_date, language, contract)
        text = str(body.get(language) or "")
        ref = str(reference.get(language) or "")
        keep_text = bool(text and exact)
        keep_reference = bool(ref and (exact or daily))

        # Explicitly quarantine the legacy Arabic eBible injection and any other
        # body that has no same-language official evidence.
        if not keep_text:
            body[language] = ""
            source[language] = ""
        if not keep_reference:
            reference[language] = ""

        if keep_text and exact:
            native_verification[language] = dict(exact)
            native_verification[language].update({
                "reference_available": bool(reference.get(language)),
                "text_available": True,
                "text_sha256": sha256_text(text),
                "ai_translation_used": False,
                "automatic_diacritization_used": False,
            })
        elif keep_reference and daily:
            evidence = daily["evidence"]
            native_verification[language] = {
                "status": "VERIFIED_EXACT_NATIVE_REFERENCE_ONLY",
                "source_id": daily["source_id"],
                "source_url": evidence.get("url"),
                "canonical_reference": canonical,
                "reference_available": True,
                "text_available": False,
                "ai_translation_used": False,
                "automatic_diacritization_used": False,
            }
        else:
            native_verification[language] = unavailable(language, canonical)

    reading["reference"] = reference
    reading["body"] = body
    reading["source"] = source
    reading["translation_locked"] = True
    reading["native_source_verification"] = native_verification
    reading.pop("translation_verification", None)
    reading["integrity"] = {
        "status": "NATIVE_LANGUAGE_LANES_ENFORCED",
        "canonical_reference": canonical,
        "display_text_changed": False,
        "legacy_cross_lane_text_removed": True,
        "ai_translation_used": False,
        "automatic_diacritization_used": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=["data/calendar/today.json"])
    args = parser.parse_args()
    contract = load_contract()
    for raw_path in args.paths:
        path = ROOT / raw_path
        data = json.loads(path.read_text(encoding="utf-8"))
        target_date = str(data.get("date_iso") or data.get("date") or "")
        for readings in reading_lists(data):
            for reading in readings:
                if isinstance(reading, dict):
                    enforce_reading(reading, data, target_date, contract)
        data["schema_version"] = max(9, int(data.get("schema_version") or 0))
        data["language_content_mode"] = "THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES"
        data["machine_translation_used"] = False
        data["automatic_diacritization_used"] = False
        data["translation_fallback_policy"] = "DISABLED_NO_CROSS_LANGUAGE_FALLBACK"
        data["native_text_contract"] = "canonical/source_native_contract.json"
        data["language_sources"] = {
            lang: {
                "priority": contract["language_lanes"][lang]["priority"],
                "same_language_fallback_only": True,
                "machine_translation_used": False,
                "automatic_diacritization_used": False,
                "missing_text_behavior": "UNAVAILABLE",
            } for lang in LANGUAGES
        }
        publication = data.setdefault("publication", {})
        publication["status"] = "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED"
        publication["fail_closed"] = True
        publication["same_language_fallback_only"] = True
        publication["religious_text_contract"] = "canonical/source_native_contract.json"

        top_integrity = data.setdefault("integrity", {})
        top_integrity.pop("canonical_id", None)
        top_integrity.pop("canonical_revision", None)
        top_integrity.pop("vocalized_source_id", None)
        top_integrity["native_text_contract"] = "canonical/source_native_contract.json"
        top_integrity["legacy_arabic_scripture_snapshot"] = "QUARANTINED_NOT_PUBLICATION_AUTHORITY"

        metadata = data.setdefault("content_metadata", {})
        metadata["review_status"] = "automatic_native_language_policy_enforced"

        for evidence in data.get("source_evidence") or []:
            if not isinstance(evidence, dict):
                continue
            reason = str(evidence.get("reason") or "")
            if "نص الآيات العربي يؤخذ" in reason:
                evidence["reason"] = reason.split("نص الآيات العربي يؤخذ", 1)[0].rstrip(" .؛") + "."

        for service in data.get("services") or []:
            if not isinstance(service, dict):
                continue
            integrity = service.get("integrity")
            if isinstance(integrity, dict) and integrity.get("status") in {"VERIFIED_DYNAMIC_PROPERS_AND_EXACT_SCRIPTURE", "VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED"}:
                integrity["status"] = "VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED"
                integrity["scripture"] = "PER_LANGUAGE_OFFICIAL_NATIVE_CORPUS_OR_UNAVAILABLE"
                integrity["machine_translation_used"] = False
                integrity["automatic_diacritization_used"] = False

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Enforced independent native-language lanes in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
