#!/usr/bin/env python3
"""Validate daily religious content without requiring every language to be filled."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, script_errors

SCRIPTURE_KINDS = {"prokeimenon", "epistle", "gospel"}
ALLOWED_STATUSES = {
    "VERIFIED_EXACT_NATIVE_SOURCE",
    "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
    "VERIFIED_EXACT_NATIVE_REFERENCE_ONLY",
    "UNAVAILABLE_UNTIL_EXACT_OFFICIAL_NATIVE_SOURCE",
}


def reading_lists(data: dict[str, Any]) -> Iterable[tuple[str, list[Any]]]:
    if isinstance(data.get("readings"), list):
        yield "readings", data["readings"]
    sunday = data.get("next_sunday")
    if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
        yield "next_sunday.readings", sunday["readings"]
    integrity_inputs = data.get("integrity_inputs")
    if isinstance(integrity_inputs, dict):
        sunday = integrity_inputs.get("next_sunday")
        if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
            yield "integrity_inputs.next_sunday.readings", sunday["readings"]
    for index, service in enumerate(data.get("services") or []):
        if isinstance(service, dict) and isinstance(service.get("readings"), list):
            yield f"services[{index}].readings", service["readings"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--require-complete", action="store_true", help="deprecated: prints coverage but never forces translation")
    args = parser.parse_args()
    data = json.loads((ROOT / args.path).read_text(encoding="utf-8"))
    contract = load_contract()
    errors: list[str] = []
    coverage = {lang: {"references": 0, "texts": 0, "total": 0} for lang in LANGUAGES}

    if data.get("language_content_mode") != "THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES":
        errors.append("daily language_content_mode is invalid")
    if data.get("machine_translation_used") is not False or data.get("automatic_diacritization_used") is not False:
        errors.append("daily forbidden transformation flags must be false")
    if data.get("translation_fallback_policy") != "DISABLED_NO_CROSS_LANGUAGE_FALLBACK":
        errors.append("cross-language fallback must be disabled")

    for pointer, readings in reading_lists(data):
        for index, reading in enumerate(readings):
            if not isinstance(reading, dict) or reading.get("kind") not in SCRIPTURE_KINDS:
                continue
            refs = reading.get("reference") if isinstance(reading.get("reference"), dict) else {}
            bodies = reading.get("body") if isinstance(reading.get("body"), dict) else {}
            verification = reading.get("native_source_verification") if isinstance(reading.get("native_source_verification"), dict) else {}
            for lang in LANGUAGES:
                coverage[lang]["total"] += 1
                ref = str(refs.get(lang) or "")
                text = str(bodies.get(lang) or "")
                if ref: coverage[lang]["references"] += 1
                if text: coverage[lang]["texts"] += 1
                evidence = verification.get(lang)
                if not isinstance(evidence, dict) or evidence.get("status") not in ALLOWED_STATUSES:
                    errors.append(f"{pointer}[{index}].{lang}: missing native verification")
                    continue
                if evidence.get("ai_translation_used") is not False or evidence.get("automatic_diacritization_used") is not False:
                    errors.append(f"{pointer}[{index}].{lang}: forbidden transformation flag")
                source_id = str(evidence.get("source_id") or "")
                if (ref or text) and not source_allowed(lang, source_id, contract):
                    errors.append(f"{pointer}[{index}].{lang}: source {source_id!r} is outside language lane")
                if text:
                    if evidence.get("status") not in {"VERIFIED_EXACT_NATIVE_SOURCE", "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS"}:
                        errors.append(f"{pointer}[{index}].{lang}: non-empty text is not exact-source verified")
                    if evidence.get("text_sha256") != sha256_text(text):
                        errors.append(f"{pointer}[{index}].{lang}: text hash mismatch")
                    for error in script_errors(lang, text):
                        errors.append(f"{pointer}[{index}].{lang}: {error}")
                if not text and evidence.get("text_available") is True:
                    errors.append(f"{pointer}[{index}].{lang}: evidence says text is available but body is empty")
                if not ref and evidence.get("reference_available") is True:
                    errors.append(f"{pointer}[{index}].{lang}: evidence says reference is available but reference is empty")

    for lang, stats in coverage.items():
        print(f"daily {lang}: references {stats['references']}/{stats['total']}; exact texts {stats['texts']}/{stats['total']}")
    if args.require_complete:
        print("NOTE: --require-complete no longer forces cross-language completion; missing native text is safely unavailable.")
    if errors:
        raise SystemExit("\n".join(dict.fromkeys(errors)))
    print("Daily native-language lanes validated")


if __name__ == "__main__":
    main()
