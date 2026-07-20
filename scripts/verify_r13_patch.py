#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.9"', "versionCode = 50009"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R13"', "validate_fasting_guidance.py"),
    "scripts/update_liturgical_data.py": (
        'data["fasting_guidance_version"] = 1',
        '"allowed_summary"',
        '"abstinence"',
    ),
    "scripts/validate_fasting_guidance.py": ("EXPECTED_ALLOWED", "documented_interval"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java": ("addFastingGuide", "Total abstinence"),
}
missing = []
for relative, markers in checks.items():
    path = ROOT / relative
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for marker in markers:
        if marker not in text:
            missing.append(f"{relative}: {marker}")
if missing:
    raise SystemExit(
        "PATCH_R13_NOT_APPLIED\n"
        + "\n".join(missing)
        + "\nExtract the R13 rootless changes ZIP directly into the repository root and overwrite existing files."
    )
print("PATCH_R13_OK version=5.0.9 level=R13")
