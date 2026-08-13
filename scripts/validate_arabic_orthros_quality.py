#!/usr/bin/env python3
"""Validate the clean authorized Arabic Orthros import."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    override = load("data/services/native_overrides/ar/orthros.json")
    if override.get("displayable") is not True:
        errors.append("clean Arabic Orthros must be displayable")
    if override.get("publication_status") != "DISPLAYABLE_COMPLETE_AUTHORIZED_NATIVE_SOURCE":
        errors.append("Arabic Orthros complete publication status is missing")
    if len(override.get("segments") or []) < 150:
        errors.append("Arabic Orthros is unexpectedly short")
    source = override.get("source_document") or {}
    if source.get("source_id") != "orthodox_jordan_arabic_services" or not source.get("source_sha256"):
        errors.append("Arabic Orthros source evidence is missing")
    visible = "\n".join(str((segment.get("text") or {}).get("ar") or "") for segment in override.get("segments") or [])
    if "الناهضمن" in visible or "السوائي الكبير" in visible:
        errors.append("historical corrupt OCR leaked into the clean Orthros")

    core = load("app/src/main/assets/data/native/arabic_office_reader_core.json")
    if core.get("language") != "ar" or core.get("policy") != "READER_SAFE_CORE_FAIL_CLOSED":
        errors.append("Arabic office reader-safe core metadata is invalid")
    orthros = next((item for item in core.get("services", []) if item.get("id") == "orthros"), None)
    if not orthros or len(orthros.get("segments", [])) < 5:
        errors.append("legacy reader-safe core is unexpectedly missing")

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
    if manifest["languages"]["ar"]["orthros"] != "complete_exact_native_edition":
        errors.append("Arabic Orthros completeness status is not exact")

    if errors:
        raise SystemExit("ARABIC_ORTHROS_QUALITY_FAILED\n- " + "\n- ".join(errors))
    print("ARABIC_ORTHROS_QUALITY_OK clean_authorized_source=true search_safe=true exact_native_edition=true")


if __name__ == "__main__":
    main()
