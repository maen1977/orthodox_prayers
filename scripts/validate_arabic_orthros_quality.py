#!/usr/bin/env python3
"""Keep the unreadable Arabic Orthros OCR fail-closed until a clean import exists."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    override = load("data/services/native_overrides/ar/orthros.json")
    if override.get("displayable") is not False:
        errors.append("Arabic Orthros OCR must remain non-displayable")
    if override.get("publication_status") != "BLOCKED_ARABIC_OCR_REIMPORT_REQUIRED":
        errors.append("Arabic Orthros publication block is missing")
    review = override.get("quality_review") or {}
    if review.get("automatic_ocr_publication_allowed") is not False:
        errors.append("automatic OCR publication must remain forbidden")
    if review.get("ai_rewriting_or_correction_allowed") is not False:
        errors.append("AI rewriting/correction must remain forbidden")

    for relative in (
        "data/services/native/library_ar.json",
        "app/src/main/assets/data/native/library_ar.json",
    ):
        pack = load(relative)
        service = next((item for item in pack.get("services", []) if item.get("id") == "orthros"), None)
        if not service or service.get("displayable") is not False:
            errors.append(f"{relative}: blocked Arabic Orthros metadata missing")

    search = load("app/src/main/assets/data/search/search_index_ar.json")
    if any(item.get("id") == "service:orthros" for item in search.get("documents", [])):
        errors.append("blocked Arabic Orthros leaked into search")

    manifest = load("canonical/religious_completeness_manifest.json")
    if manifest["languages"]["ar"]["orthros"] != "source_text_partial":
        errors.append("Arabic Orthros completeness claim is not fail-closed")

    if errors:
        raise SystemExit("ARABIC_ORTHROS_QUALITY_FAILED\n- " + "\n- ".join(errors))
    print("ARABIC_ORTHROS_QUALITY_OK displayable=false search=false clean_source_required=true")


if __name__ == "__main__":
    main()
