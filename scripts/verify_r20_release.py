#!/usr/bin/env python3
"""Fail early when any mandatory R20 religious-integrity component is absent."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "app/build.gradle.kts": ('versionName = "5.0.16"', "versionCode = 50016"),
    "scripts/public_domain_scripture.py": (r"\\\+?w",),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DisplayTextSanitizer.java": (
        "class DisplayTextSanitizer",
        "WORD_MARKER",
    ),
    "scripts/build_native_service_packs.py": (
        "annotate_dynamic_slots",
        "dynamic_slot",
    ),
    "scripts/update_liturgical_data.py": (
        '"slot_replacements"',
        '"slot_inline_replacements"',
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java": (
        "applyDynamicSlotReplacements",
        "legacyDynamicSlots",
        "isLegacyPlaceholderMarker",
        "religiousCompleteServiceCount",
    ),
    "scripts/update_language_lane.py": (
        "other two languages",
        "keep_only_language",
    ),
    "scripts/verify_language_lanes.py": (
        "isolation_error",
        "language lane is not isolated",
    ),
    "canonical/religious_completeness_manifest.json": (
        '"chrysostom_liturgy"',
        '"production_complete_status": "complete_exact_native_edition"',
    ),
    "scripts/validate_religious_completeness.py": (
        "--require-production-complete",
        "RELIGIOUS_COMPLETENESS_OK",
    ),
    "tests/test_r20_religious_completeness.py": (
        "class R20ReligiousCompletenessTests",
    ),
}


def main() -> None:
    missing: list[str] = []
    for relative, markers in REQUIRED.items():
        path = ROOT / relative
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker not in content:
                missing.append(f"{relative}: {marker}")
    if missing:
        raise SystemExit("R20_PARTIAL_OR_MISPLACED\n" + "\n".join(missing))
    print("R20_RELEASE_OK version=5.0.16 level=R20")


if __name__ == "__main__":
    main()
