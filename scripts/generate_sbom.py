#!/usr/bin/env python3
"""Generate a CycloneDX JSON SBOM from Gradle's resolved report or declared dependencies."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORDINATE = re.compile(r"(?:---|\\---|\\+---)\s+([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([^\s()]+)")
DECLARED = re.compile(r'(?:implementation|testImplementation|androidTestImplementation)\("([^:"]+):([^:"]+):([^"]+)"\)')
PLUGIN = re.compile(r'id\("([^"]+)"\) version "([^"]+)"')


def components(report: Path | None) -> list[dict]:
    found: set[tuple[str, str, str, str]] = set()
    if report and report.is_file():
        for group, name, version in COORDINATE.findall(report.read_text(encoding="utf-8", errors="replace")):
            found.add(("library", group, name, version))
    for path in (ROOT / "app/build.gradle.kts", ROOT / "build.gradle.kts"):
        text = path.read_text(encoding="utf-8")
        for group, name, version in DECLARED.findall(text):
            found.add(("library", group, name, version))
        for name, version in PLUGIN.findall(text):
            found.add(("framework", "gradle-plugin", name, version))
    result = []
    for kind, group, name, version in sorted(found):
        result.append({
            "type": kind,
            "group": group,
            "name": name,
            "version": version,
            "purl": f"pkg:maven/{group}/{name}@{version}",
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gradle-report", type=Path)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = None if args.gradle_report is None else (args.gradle_report if args.gradle_report.is_absolute() else ROOT / args.gradle_report)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:6d1b3f2a-e3dc-5000-9000-0a7d0d0a5000",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "application",
                "name": "Orthodox Prayers",
                "version": "5.0.1",
                "purl": "pkg:android/com.orthodoxprayers.privateapp@5.0.1",
            },
        },
        "components": components(report),
    }
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SBOM created: {output} ({len(document['components'])} components)")


if __name__ == "__main__":
    main()
