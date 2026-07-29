#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from official_sources import validate_source_order
ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / "data/calendar/today.json"

def main() -> None:
    errors = validate_source_order()
    data = json.loads(TODAY.read_text(encoding="utf-8"))
    publication = data.get("publication", {})
    if publication.get("status") != "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED":
        errors.append("Today data is not marked AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED")
    if publication.get("fail_closed") is not True:
        errors.append("Today data does not declare fail_closed=true")
    if publication.get("same_language_fallback_only") is not True:
        errors.append("Today data does not enforce same-language fallback only")
    if publication.get("religious_text_contract") != "canonical/source_native_contract.json":
        errors.append("Today data does not identify the native source contract")
    evidence = data.get("source_evidence")
    if not isinstance(evidence, list):
        errors.append("Today source_evidence must be a list")
    selected_source = publication.get("selected_source")
    availability = publication.get("daily_availability")
    if selected_source and not evidence:
        errors.append("Today selected an official calendar source without source_evidence")
    if not selected_source and availability not in {"PARTIAL_VERIFIED", "FULL"}:
        errors.append("Today has neither selected source evidence nor an allowed fail-closed availability state")
    lanes = data.get("language_sources") or {}
    for lang in ("ar", "en", "el"):
        lane = lanes.get(lang) or {}
        if lane.get("same_language_fallback_only") is not True:
            errors.append(f"{lang} lane is not fail-closed to same-language sources")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Official calendar evidence/fail-closed state and independent native-language publication policy validated")

if __name__ == "__main__":
    main()
