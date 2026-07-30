#!/usr/bin/env python3
"""Build one truthful completion dashboard from the canonical manifest."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "canonical" / "religious_completeness_manifest.json"
OUTPUT = ROOT / "MASTER_COMPLETION_AUDIT.json"
LANGUAGES = ("ar", "en", "el")
EXACT = "complete_exact_native_edition"
COMPILATION = "complete_native_source_compilation"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    required = manifest["required_services"]
    complete_statuses = set(manifest.get("production_complete_statuses") or [EXACT])
    rows = []
    for service in required:
        row = {
            "service": service,
            "packaged_service_id": manifest["packaged_service_ids"].get(service),
            "languages": {},
        }
        for language in LANGUAGES:
            status = manifest["languages"][language][service]
            row["languages"][language] = {
                "status": status,
                "technical_release_ready": status in complete_statuses,
                "single_exact_edition": status == EXACT,
                "native_source_compilation": status == COMPILATION,
            }
        row["all_languages_technical_release_ready"] = all(
            row["languages"][language]["technical_release_ready"] for language in LANGUAGES
        )
        rows.append(row)

    summary = {}
    for language in LANGUAGES:
        statuses = [manifest["languages"][language][service] for service in required]
        summary[language] = {
            "technical_complete": sum(status in complete_statuses for status in statuses),
            "exact_single_edition": statuses.count(EXACT),
            "native_source_compilation": statuses.count(COMPILATION),
            "required": len(required),
        }

    output = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "technical_release_allowed": all(
            summary[language]["technical_complete"] == len(required) for language in LANGUAGES
        ),
        "ecclesiastical_approval_certified": bool(manifest.get("ecclesiastical_approval_certified", False)),
        "definition": manifest["definition"],
        "machine_translation_allowed": manifest["machine_translation_allowed"],
        "production_complete_statuses": sorted(complete_statuses),
        "summary": summary,
        "services": rows,
        "release_rules": [
            "Every required service must be technically complete in Arabic, English, and Greek.",
            "A complete native-source compilation remains labeled separately from one exact edition.",
            "A fragment, abridgement, external link, or machine translation is not technical completeness.",
            "Technical completeness does not claim ecclesiastical review or blessing.",
        ],
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)
    print(json.dumps(summary, ensure_ascii=False))
    print("technical_release_allowed=", output["technical_release_allowed"])


if __name__ == "__main__":
    main()
