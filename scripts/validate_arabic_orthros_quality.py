#!/usr/bin/env python3
"""Keep raw Arabic Orthros OCR fail-closed while requiring a readable reader-safe core."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    override = load("data/services/native_overrides/ar/orthros.json")
    # The historical OCR remains audit material and must never be presented as exact text.
    if override.get("displayable") is not False:
        errors.append("raw Arabic Orthros OCR must remain non-displayable")
    if override.get("publication_status") != "BLOCKED_ARABIC_OCR_REIMPORT_REQUIRED":
        errors.append("raw Arabic Orthros publication block is missing")
    review = override.get("quality_review") or {}
    if review.get("automatic_ocr_publication_allowed") is not False:
        errors.append("automatic OCR publication must remain forbidden")
    if review.get("ai_rewriting_or_correction_allowed") is not False:
        errors.append("AI rewriting/correction must remain forbidden")

    core = load("app/src/main/assets/data/native/arabic_office_reader_core.json")
    if core.get("language") != "ar" or core.get("policy") != "READER_SAFE_CORE_FAIL_CLOSED":
        errors.append("Arabic office reader-safe core metadata is invalid")
    orthros = next((item for item in core.get("services", []) if item.get("id") == "orthros"), None)
    if not orthros or orthros.get("raw_ocr_hidden_from_reader") is not True:
        errors.append("readable Arabic Orthros core is missing")
    elif len(orthros.get("segments", [])) < 5:
        errors.append("readable Arabic Orthros core is unexpectedly empty")

    text = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    if 'arabicOfficeReadableCore(id)' not in text or 'arabic_office_reader_core.json' not in text:
        errors.append("Android reader does not use the Arabic office safe core")
    if "arabicOfficeSourceQualityNotice" in text:
        errors.append("obsolete no-prayer Orthros notice is still wired into the reader")

    search = load("app/src/main/assets/data/search/search_index_ar.json")
    doc = next((item for item in search.get("documents", []) if item.get("id") == "service:orthros"), None)
    if not doc:
        errors.append("readable Arabic Orthros is missing from search")
    elif "الناهضمن" in doc.get("display_text", "") or "السوائي الكبير" in doc.get("display_text", ""):
        errors.append("raw Orthros OCR leaked into search")

    manifest = load("canonical/religious_completeness_manifest.json")
    if manifest["languages"]["ar"]["orthros"] != "source_text_partial":
        errors.append("Arabic Orthros completeness must remain fail-closed until a full exact import exists")

    if errors:
        raise SystemExit("ARABIC_ORTHROS_QUALITY_FAILED\n- " + "\n- ".join(errors))
    print("ARABIC_ORTHROS_QUALITY_OK raw_ocr=blocked reader_safe_core=true search_safe=true full_exact_claim=false")


if __name__ == "__main__":
    main()
