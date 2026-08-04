#!/usr/bin/env python3
"""Verify that the R18 source-intelligence patch is present at repository root."""
from pathlib import Path

from release_version import require_minimum

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R18.4"', "collect_source_health.py", "attach_source_intelligence.py", "clean_legacy_calendar_snapshots.py"),
    "scripts/orthodox_integrity.py": ('"Mt.": "Matthew"', "_monitored_dcs_regular_cycle_evidence"),
    "scripts/source_connectors.py": ("dcs_reference_after_heading", "DCS regular-cycle references extracted"),
    "canonical/source_connectors.json": ('"local_authority_source_id": "orthodox_jordan"', '"goarch_digital_chant_stand"'),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/SearchEngine.java": ("scanChurches", "officialServiceLinks", "editDistanceAtMostOne"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ChurchesScreen.java": ("ui_church_directory_36e0707d", "officialServiceLinks"),
    ".github/workflows/update.yml": ("ORTHODOX_ENABLE_LIVE_SOURCE_FETCH", "validate_source_intelligence.py", "clean_legacy_calendar_snapshots.py\" --root \"$TARGET"),
    ".github/workflows/build.yml": ("clean_legacy_calendar_snapshots.py --root \"$VERIFIED_DIR\"", "--allow-missing-manifest"),
    "scripts/verify.py": ("--allow-missing-manifest", "LEGACY_UPDATE_MANIFEST_ABSENT"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java": ("addLanguageButton", "addReminder"),
    "tests/test_r18_3_settings_compile_hotfix.py": ("test_settings_screen_hides_technical_coverage_badges", "liturgyCoverageBadge\" not in source"),
    "tests/test_r18_4_dcs_mt_abbreviation_hotfix.py": ("Mt. 16:6 - 12", "test_cross_chapter_dcs_reference_remains_parseable"),
}
version_name, version_code = require_minimum(50023)
missing = []
for relative, markers in REQUIRED.items():
    path = ROOT / relative
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for marker in markers:
        if marker not in text:
            missing.append(f"{relative}: {marker}")
if missing:
    raise SystemExit("PATCH_R18_NOT_APPLIED\n" + "\n".join(missing))
print(f"PATCH_R18_OK version={version_name} code={version_code} level=R18.4 refinement=R20")
