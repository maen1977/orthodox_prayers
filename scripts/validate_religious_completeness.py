#!/usr/bin/env python3
"""Validate honest service-level religious completeness declarations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "canonical/religious_completeness_manifest.json"
APP_ASSET = ROOT / "app/src/main/assets/data/religious_completeness.json"
PACK_DIR = ROOT / "data/services/native"
LANGUAGES = ("ar", "en", "el")
ALLOWED_STATUSES = {
    "complete_exact_native_edition",
    "abridged",
    "unproven_complete",
    "source_text_partial",
    "unavailable_notice",
    "missing",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-production-complete", action="store_true")
    args = parser.parse_args()

    manifest_bytes = MANIFEST.read_bytes()
    if not APP_ASSET.is_file() or APP_ASSET.read_bytes() != manifest_bytes:
        raise SystemExit(
            "Religious completeness validation failed:\n"
            "- Android completeness asset must be byte-identical to the canonical manifest"
        )
    manifest = json.loads(manifest_bytes)
    required = manifest.get("required_services")
    mappings = manifest.get("packaged_service_ids")
    languages = manifest.get("languages")
    errors: list[str] = []
    if not isinstance(required, list) or len(required) != 15 or len(set(required)) != 15:
        errors.append("required_services must contain exactly 15 unique services")
        required = required if isinstance(required, list) else []
    if set(mappings or {}) != set(required):
        errors.append("packaged_service_ids must match required_services")
    if manifest.get("machine_translation_allowed") is not False:
        errors.append("machine translation must remain forbidden")

    summaries: dict[str, tuple[int, int]] = {}
    for language in LANGUAGES:
        pack = json.loads((PACK_DIR / f"library_{language}.json").read_text(encoding="utf-8"))
        packaged_ids = {
            item.get("id") for item in pack.get("services", []) if isinstance(item, dict)
        }
        statuses = (languages or {}).get(language)
        if not isinstance(statuses, dict) or set(statuses) != set(required):
            errors.append(f"{language}: completeness statuses do not match required services")
            statuses = statuses if isinstance(statuses, dict) else {}
        complete = 0
        for service_id in required:
            status = statuses.get(service_id)
            if status not in ALLOWED_STATUSES:
                errors.append(f"{language}.{service_id}: unsupported status {status!r}")
                continue
            packaged_id = (mappings or {}).get(service_id)
            if status == "missing" and packaged_id is not None:
                errors.append(f"{language}.{service_id}: missing status has a packaged service")
            if status != "missing" and packaged_id not in packaged_ids:
                errors.append(f"{language}.{service_id}: declared service is not packaged")
            if status == "complete_exact_native_edition":
                complete += 1
        summaries[language] = (complete, len(required))
        if args.require_production_complete and complete != len(required):
            errors.append(
                f"{language}: production completeness is {complete}/{len(required)}"
            )

    for language, (complete, total) in summaries.items():
        print(f"RELIGIOUS_COMPLETENESS language={language} verified_complete={complete}/{total}")
    if errors:
        raise SystemExit("Religious completeness validation failed:\n- " + "\n- ".join(errors))
    mode = "production" if args.require_production_complete else "declaration"
    print(f"RELIGIOUS_COMPLETENESS_OK mode={mode}")


if __name__ == "__main__":
    main()
