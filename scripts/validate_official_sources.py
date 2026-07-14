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
    if not isinstance(evidence, list) or not evidence:
        errors.append("Today data has no source_evidence")
    lanes = data.get("language_sources") or {}
    for lang in ("ar", "en", "el"):
        lane = lanes.get(lang) or {}
        if lane.get("same_language_fallback_only") is not True:
            errors.append(f"{lang} lane is not fail-closed to same-language sources")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Official calendar evidence and independent native-language publication policy validated")

if __name__ == "__main__":
    main()
