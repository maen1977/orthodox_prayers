#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.11"', "versionCode = 50011"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R15"', "R15_THEME_PALETTE_IMPORT", "R14_SETTINGS_CLEANUP"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java": (
        "R15_THEME_PALETTE_IMPORT",
        "import com.orthodoxprayers.privateapp.ui.ThemePalette;",
        "ThemePalette.NAVY",
        "ThemePalette.GOLD",
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
        "PATCH_R15_NOT_APPLIED\n"
        + "\n".join(missing)
        + "\nExtract the R15 rootless changes ZIP directly into the repository root and overwrite existing files."
    )
print("PATCH_R15_OK version=5.0.11 level=R15")
