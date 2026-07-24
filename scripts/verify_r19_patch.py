#!/usr/bin/env python3
"""Fail early when the R19 source patch was extracted only partially."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "app/build.gradle.kts": ('versionName = "5.0.16"', "versionCode = 50016"),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java": (
        "libraryForLanguage(language)",
        "nativeContentCoverage",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/TranslationCoverage.java": (
        'if ("ar".equals(language))',
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java": (
        "advancedDiagnosticsExpanded",
        "resetReaderPreferences",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/LocalePolicy.java": (
        "localeForLanguage",
        "isolateTechnical",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java": (
        'data.religiousCompleteServiceCount("ar")',
        'data.religiousCompleteServiceCount("en")',
        'data.religiousCompleteServiceCount("el")',
        "new TimePicker",
        "LocalePolicy.formatTimestamp",
    ),
    "scripts/build_public_source_registry.py": (
        '"last_verified": latest[:10]',
    ),
    "scripts/orthodox_integrity.py": (
        "canonical_reference_is_valid",
        "CANONICAL_REFERENCE_PART_RE",
    ),
    "scripts/fill_daily_from_native_corpora.py": (
        "parse_reference_parts",
        "CanonicalSpans",
    ),
    "canonical/source_native_contract.json": (
        '"verification_mode": "same_workflow_after_publish"',
    ),
    "tests/test_r19_refinement.py": (
        "class R19RefinementTests",
        'versionName = "5.0.16"',
    ),
}


def missing_markers() -> list[str]:
    missing: list[str] = []
    for relative, markers in REQUIRED.items():
        path = ROOT / relative
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker not in content:
                missing.append(f"{relative}: {marker}")
    return missing


def main() -> None:
    missing = missing_markers()
    if missing:
        details = "\n".join(missing)
        raise SystemExit(
            "PATCH_R19_PARTIAL_OR_MISPLACED\n"
            f"{details}\n"
            "Extract OrthodoxPrayers-5.0.15-R19.1-root-patch.zip directly into "
            "the repository root and overwrite existing files."
        )
    print("PATCH_R19_OK version=5.0.16 level=R19.2+R20")


if __name__ == "__main__":
    main()
