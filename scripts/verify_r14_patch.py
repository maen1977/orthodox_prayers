#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "app/build.gradle.kts": ('versionName = "5.0.10"', "versionCode = 50010"),
    "scripts/update.py": ('PIPELINE_PATCH_LEVEL = "R14"', "R14_HOME_COMPACT", "R14_SETTINGS_CLEANUP"),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java": (
        "R14_HOME_COMPACT",
        "الصلوات الكنسية",
        "addCompactFastingItems(card, fasting)",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java": (
        "✓ مسموح   ✕ ممنوع",
        "addCompactFastingItems",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java": (
        "R14_SETTINGS_CLEANUP",
        "هذا البرنامج مجاني",
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
        "PATCH_R14_NOT_APPLIED\n"
        + "\n".join(missing)
        + "\nExtract the R14 rootless changes ZIP directly into the repository root and overwrite existing files."
    )

home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
for forbidden in ("addStatusCard(page.root)", "addTodayFastingGuide(page.root)", 'local("بحث", "Search"', 'local("المفضلة", "Favorites"', 'local("التقويم", "Calendar"', 'local("حزم اللغات", "Language packs"'):
    if forbidden in home:
        missing.append(f"HomeScreen still contains hidden home action: {forbidden}")
for forbidden in ("الاتصال بالرقم", "Call phone number", "سياسة الخصوصية", "Privacy policy", "maen1977.github.io/orthodox_prayers/privacy"):
    if forbidden in settings:
        missing.append(f"SettingsScreen still contains removed action: {forbidden}")
if missing:
    raise SystemExit("PATCH_R14_UI_CONTRACT_FAILED\n" + "\n".join(missing))
print("PATCH_R14_OK version=5.0.10 level=R14")
