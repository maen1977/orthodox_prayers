#!/usr/bin/env python3
"""Attach source-health, church-directory, service-link, and coverage metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from source_connectors import ROOT

HEALTH = ROOT / "data" / "sources" / "health" / "current.json"
CHURCHES = ROOT / "data" / "directory" / "churches.json"
COVERAGE_ASSET = ROOT / "app" / "src" / "main" / "assets" / "data" / "service_coverage.json"

REQUIRED_VARIABLES = {
    "divine_liturgy": [
        "[طروبارية اليوم]", "[القنداق]", "[البروكيمنن]", "[فصل من رسالة اليوم]",
        "[فصل الإنجيل المعيّن لهذا اليوم]", "[آية المناولة]",
    ],
}


def nonempty_localized(value: Any) -> bool:
    return isinstance(value, dict) and any(str(value.get(lang) or "").strip() for lang in ("ar", "en", "el"))


def coverage(data: dict[str, Any]) -> dict[str, Any]:
    services = []
    for service in data.get("services") or []:
        service_id = str(service.get("id") or "")
        replacements = service.get("segment_replacements") or {}
        required = REQUIRED_VARIABLES.get(service_id, [])
        present = [key for key in required if nonempty_localized(replacements.get(key))]
        missing = [key for key in required if key not in present]
        percent = 100 if not required else round(len(present) * 100 / len(required))
        services.append({
            "service_id": service_id,
            "required_variable_count": len(required),
            "verified_variable_count": len(present),
            "coverage_percent": percent,
            "missing_variables": missing,
            "complete": bool(required) and not missing,
        })
    return {
        "schema_version": 1,
        "claim_policy": "complete only when every required variable has verified native-language text",
        "services": services,
    }


def attach(path: Path, health: dict[str, Any], churches: dict[str, Any]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if str(health.get("date_iso")) == str(data.get("date_iso")):
        data["source_health"] = health
    else:
        data["source_health"] = {
            "schema_version": 1,
            "date_iso": data.get("date_iso"),
            "summary": {"status": "STALE_HEALTH_SNAPSHOT_REJECTED"},
            "observations": [],
        }
    data["church_directory"] = churches
    data["service_coverage"] = coverage(data)
    data["source_intelligence_contract"] = "canonical/source_connectors.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    health = json.loads(HEALTH.read_text(encoding="utf-8"))
    churches = json.loads(CHURCHES.read_text(encoding="utf-8"))
    coverage_written = False
    for value in args.paths:
        path = ROOT / value
        if path.is_file():
            if not coverage_written:
                original = json.loads(path.read_text(encoding="utf-8"))
                COVERAGE_ASSET.parent.mkdir(parents=True, exist_ok=True)
                COVERAGE_ASSET.write_text(json.dumps(coverage(original), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                coverage_written = True
            attach(path, health, churches)
            print(f"ATTACHED_SOURCE_INTELLIGENCE path={value}")


if __name__ == "__main__":
    main()
