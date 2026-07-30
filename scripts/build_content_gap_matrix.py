#!/usr/bin/env python3
"""Build a gap matrix that distinguishes exact editions from complete compilations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "canonical" / "religious_completeness_manifest.json"
OUTPUT = ROOT / "CONTENT_GAP_MATRIX.json"
LANGUAGES = ("ar", "en", "el")
EXACT = "complete_exact_native_edition"
COMPILATION = "complete_native_source_compilation"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    complete_statuses = set(manifest.get("production_complete_statuses") or [EXACT])
    required = manifest["required_services"]
    rows = []
    for service in required:
        row = {
            "service": service,
            "packaged_service_id": manifest["packaged_service_ids"][service],
            "languages": {},
        }
        for language in LANGUAGES:
            status = manifest["languages"][language][service]
            ready = status in complete_statuses
            notes = []
            if status == COMPILATION:
                notes.append(
                    "Complete same-language native-source compilation; kept distinct from a single exact edition."
                )
            elif not ready:
                notes.append("This lane still needs a complete authorized same-language source package.")
            row["languages"][language] = {
                "status": status,
                "technical_release_ready": ready,
                "remaining_blockers": [] if ready else notes,
                "classification_notes": notes if ready else [],
            }
        rows.append(row)

    summary = {}
    for language in LANGUAGES:
        statuses = [manifest["languages"][language][service] for service in required]
        summary[language] = {
            "technical_complete": sum(status in complete_statuses for status in statuses),
            "exact_single_edition": statuses.count(EXACT),
            "native_source_compilation": statuses.count(COMPILATION),
            "remaining_gaps": sum(status not in complete_statuses for status in statuses),
            "required": len(required),
        }
    output = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "services": rows,
        "source_acquisition_plan": "canonical/service_source_acquisition_plan.json",
        "ecclesiastical_approval_certified": bool(manifest.get("ecclesiastical_approval_certified", False)),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
