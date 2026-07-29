#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.12"', "versionCode = 50012"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R16"', 'validate_public_source_registry.py'),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java": ('host.navigate("sources", null)', 'المصادر والمراجع'),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SourcesScreen.java": ('class SourcesScreen', 'فتح المصدر الرسمي'),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java": ('relatedServicesBox', 'جميع المصادر والمراجع'),
    "app/src/main/assets/data/source_registry.json": ('"orthodox_jordan"', '"ebible_arabic_van_dyck"'),
}
missing=[]
for relative, markers in checks.items():
    path=ROOT/relative
    text=path.read_text(encoding='utf-8') if path.is_file() else ''
    for marker in markers:
        if marker not in text: missing.append(f"{relative}: {marker}")
if missing:
    raise SystemExit("PATCH_R16_NOT_APPLIED\n"+"\n".join(missing)+"\nExtract the R16 changes ZIP directly into the repository root and overwrite existing files.")
print("PATCH_R16_OK version=5.0.12 level=R16")
