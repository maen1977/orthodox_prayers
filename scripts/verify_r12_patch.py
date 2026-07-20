#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.8"', "versionCode = 50008"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R12"', 'validate_daily_ui_localizations.py'),
    "scripts/orthodox_integrity.py": (
        'if kind == "prokeimenon":',
        'if kind not in {"epistle", "gospel"}:',
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
        "PATCH_R12_NOT_APPLIED\n"
        + "\n".join(missing)
        + "\nExtract the R12 changes ZIP directly into the repository root and overwrite existing files."
    )
print("PATCH_R12_OK version=5.0.8 level=R12")
