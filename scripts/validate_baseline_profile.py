#!/usr/bin/env python3
"""Validate the lightweight, app-only Baseline Profile contract."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "app/src/main/baseline-prof.txt"
GRADLE = ROOT / "app/build.gradle.kts"

METHOD_RULE = re.compile(r"^[HSP]{1,3}Lcom/orthodoxprayers/privateapp/[A-Za-z0-9_$/]+;->\*\*\(\*\*\)\*\*$")
CLASS_RULE = re.compile(r"^Lcom/orthodoxprayers/privateapp/[A-Za-z0-9_$/]+;$")
REQUIRED = {
    "OrthodoxPrayersApp",
    "MainActivity",
    "DataRepository",
    "HomeScreen",
    "ReaderScreen",
    "SearchEngine",
    "CalendarScreen",
}


def main() -> None:
    if not PROFILE.is_file():
        raise SystemExit("baseline-prof.txt is missing")
    raw = PROFILE.read_text(encoding="utf-8")
    if len(raw.encode("utf-8")) > 16 * 1024:
        raise SystemExit("Baseline Profile exceeds the 16 KiB lightweight budget")

    rules = []
    for line_no, original in enumerate(raw.splitlines(), 1):
        line = original.strip()
        if not line or line.startswith("#"):
            continue
        if not (METHOD_RULE.fullmatch(line) or CLASS_RULE.fullmatch(line)):
            raise SystemExit(f"Invalid or overly broad Baseline Profile rule at line {line_no}: {line}")
        if "androidx/" in line or "java/" in line or "calendar_" in line.lower():
            raise SystemExit(f"Baseline Profile must remain app-only at line {line_no}")
        rules.append(line)

    if not rules:
        raise SystemExit("Baseline Profile contains no executable rules")
    if len(rules) > 64:
        raise SystemExit("Baseline Profile has too many rules for the Lite application")
    missing = sorted(name for name in REQUIRED if not any(f"/{name};" in rule for rule in rules))
    if missing:
        raise SystemExit("Baseline Profile misses critical journeys: " + ", ".join(missing))

    gradle = GRADLE.read_text(encoding="utf-8")
    dependency = 'implementation("androidx.profileinstaller:profileinstaller:1.4.1")'
    if gradle.count(dependency) != 1:
        raise SystemExit("Pinned ProfileInstaller 1.4.1 dependency is required exactly once")
    if "isMinifyEnabled = true" not in gradle or "isShrinkResources = true" not in gradle:
        raise SystemExit("Release optimization contract is not enabled")

    print(
        "BASELINE_PROFILE_OK "
        f"rules={len(rules)} bytes={len(raw.encode('utf-8'))} "
        "scope=app-only profileinstaller=1.4.1"
    )


if __name__ == "__main__":
    main()
