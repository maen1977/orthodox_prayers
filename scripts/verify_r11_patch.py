#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.7"', "versionCode = 50007"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R11"', "verify_pipeline_patch()"),
    "scripts/orthodox_integrity.py": ("require_complete=False",),
    "scripts/update_liturgical_data.py": (
        "require_complete: bool | None = None",
        "require_complete = source is None",
    ),
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
        "PATCH_R11_NOT_APPLIED\n"
        + "\n".join(missing)
        + "\nExtract the R11 changes ZIP directly into the repository root and overwrite existing files."
    )
print("PATCH_R11_OK version=5.0.7 level=R11")
