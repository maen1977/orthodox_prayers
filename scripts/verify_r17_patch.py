#!/usr/bin/env python3
"""Verify that the R17 update-reliability patch was applied at repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "app/build.gradle.kts": ('versionName = "5.0.23"', "versionCode = 50023"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R18.4"', "verify_pipeline_patch"),
    "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java": (
        "MORNING_REFRESH_HOUR = 4",
        "MORNING_REFRESH_MINUTE = 23",
        "scheduleDailyRefresh",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/update/RefreshPolicy.java": (
        "publicationWindow",
        "MORNING_REFRESH_HOUR",
        "shouldCheckRemoteOnResume",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java": (
        "downloadManifestSelection",
        "manifest_payload_hash_mismatch",
        "manifest_revision_rollback",
    ),
    ".github/workflows/update.yml": (
        "build_update_manifest.py",
        "sign_update_manifest.py",
        "validate_publication_consistency.py",
    ),
}
missing = []
for name, markers in REQUIRED.items():
    path = ROOT / name
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for marker in markers:
        if marker not in text:
            missing.append(f"{name}: {marker}")
if missing:
    raise SystemExit(
        "PATCH_R17_NOT_APPLIED\n" + "\n".join(missing)
        + "\nExtract the R17 changes ZIP directly into the repository root and overwrite existing files."
    )
print("PATCH_R17_OK version=5.0.23 level=R17+R37.1")
