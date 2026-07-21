#!/usr/bin/env python3
"""Verify that the R18 source-intelligence patch is present at repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "app/build.gradle.kts": ('versionName = "5.0.14"', "versionCode = 50014"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R18"', "collect_source_health.py", "attach_source_intelligence.py", "clean_legacy_calendar_snapshots.py"),
    "canonical/source_connectors.json": ('"local_authority_source_id": "orthodox_jordan"', '"goarch_digital_chant_stand"'),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/SearchEngine.java": ("scanChurches", "officialServiceLinks", "editDistanceAtMostOne"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ChurchesScreen.java": ("Church directory", "officialServiceLinks"),
    ".github/workflows/update.yml": ("ORTHODOX_ENABLE_LIVE_SOURCE_FETCH", "validate_source_intelligence.py", "clean_legacy_calendar_snapshots.py\" --root \"$TARGET"),
    ".github/workflows/build.yml": ("clean_legacy_calendar_snapshots.py --root \"$VERIFIED_DIR\"", "--allow-missing-manifest"),
    "scripts/verify.py": ("--allow-missing-manifest", "LEGACY_UPDATE_MANIFEST_ABSENT"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java": ("TextView liturgyCoverageBadge =", "add(page.root, liturgyCoverageBadge, 0, 7);"),
    "tests/test_r18_3_settings_compile_hotfix.py": ("source.count(\"TextView coverage =\") == 1", "TextView liturgyCoverageBadge ="),
}
missing = []
for relative, markers in REQUIRED.items():
    path = ROOT / relative
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for marker in markers:
        if marker not in text:
            missing.append(f"{relative}: {marker}")
if missing:
    raise SystemExit("PATCH_R18_NOT_APPLIED\n" + "\n".join(missing))
print("PATCH_R18_OK version=5.0.14 level=R18.3")
