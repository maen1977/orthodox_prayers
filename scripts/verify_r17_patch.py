#!/usr/bin/env python3
"""Verify the network-free local Daily Update architecture."""
from pathlib import Path
from release_version import require_minimum

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java": (
        "LOCAL_REFRESH_HOUR = 0",
        "LOCAL_REFRESH_MINUTE = 3",
        "scheduleDailyRefresh",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/update/RefreshPolicy.java": (
        "local daily refresh behavior",
        "shouldRefresh",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java": (
        "LocalDailyContentEngine",
        "updated_local_offline",
        "local_offline_current",
    ),
    "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java": (
        "No network connection, GitHub workflow",
        "data/calendar/calendar_",
        "network_required",
    ),
    "scripts/validate_local_daily_engine.py": ("LOCAL_DAILY_ENGINE_OK",),
}
version_name, version_code = require_minimum(50300)
missing = []
for name, markers in REQUIRED.items():
    path = ROOT / name
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for marker in markers:
        if marker not in text:
            missing.append(f"{name}: {marker}")
if (ROOT / ".github/workflows/update.yml").exists():
    missing.append(".github/workflows/update.yml: scheduled Daily Update must be removed")
if missing:
    raise SystemExit("LOCAL_DAILY_PATCH_NOT_APPLIED\n" + "\n".join(missing))
print(f"LOCAL_DAILY_PATCH_OK version={version_name} code={version_code} schedule=00:03 network=false")
