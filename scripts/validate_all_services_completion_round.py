#!/usr/bin/env python3
"""Validate the all-services one-round contract and optional production state."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "canonical/all_services_completion_round.json"
TEMPLATE = ROOT / "canonical/all_services_source_bundle.template.json"
MANIFEST = ROOT / "canonical/religious_completeness_manifest.json"
LANGS = ("ar", "en", "el")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    required = manifest.get("required_services") or []
    if contract.get("required_services") != required or len(required) != 15:
        errors.append("contract must match the canonical 15-service list")
    if contract.get("languages") != list(LANGS):
        errors.append("contract languages must be ar, en, el")
    lanes = contract.get("lanes") if isinstance(contract.get("lanes"), dict) else {}
    expected_keys = {f"{service}:{lang}" for service in required for lang in LANGS}
    if set(lanes) != expected_keys or contract.get("total_lanes") != 45:
        errors.append("contract must contain exactly 45 unique service-language lanes")
    exact = []
    incomplete = []
    for key in sorted(expected_keys):
        lane = lanes.get(key) or {}
        service, lang = key.rsplit(":", 1)
        status = manifest["languages"][lang][service]
        if lane.get("current_status") != status:
            errors.append(f"{key}: current status diverges from completeness manifest")
        is_exact = status == "complete_exact_native_edition"
        if lane.get("already_release_ready") is not is_exact:
            errors.append(f"{key}: already_release_ready flag mismatch")
        (exact if is_exact else incomplete).append(key)
        if lane.get("source_file_required") is not (not is_exact):
            errors.append(f"{key}: source_file_required mismatch")
        if lane.get("language") != lang or lane.get("service") != service:
            errors.append(f"{key}: lane identity mismatch")
        if not str(lane.get("service_id") or ""):
            errors.append(f"{key}: service_id missing")
        if int(lane.get("minimum_characters") or 0) < 1000 or int(lane.get("minimum_paragraphs") or 0) < 10:
            errors.append(f"{key}: structural minimum is too weak")
        if len(lane.get("anchors") or []) < 3:
            errors.append(f"{key}: at least three same-language anchors are required")
        if not urlparse(str(lane.get("registered_source_url") or "")).hostname:
            errors.append(f"{key}: registered source URL is invalid")
    if contract.get("current_exact_lanes") != exact:
        errors.append("current_exact_lanes is not deterministic")
    if contract.get("required_new_source_lanes") != incomplete:
        errors.append("required_new_source_lanes is not deterministic")
    if contract.get("machine_translation_allowed") is not False:
        errors.append("machine translation must remain forbidden")
    if contract.get("ai_rewriting_or_correction_allowed") is not False:
        errors.append("AI rewriting/correction must remain forbidden")
    if contract.get("automatic_ocr_publication_allowed") is not False:
        errors.append("automatic OCR publication must remain forbidden")
    entries = template.get("entries") if isinstance(template.get("entries"), dict) else {}
    if set(entries) != set(incomplete):
        errors.append("source-bundle template must contain every and only incomplete lane")
    if template.get("required_entry_count") != len(incomplete):
        errors.append("source-bundle required_entry_count must match incomplete lanes")
    for key, entry in entries.items():
        if entry.get("permission_confirmed") is not False:
            errors.append(f"{key}: template must not pre-claim permission")
        if entry.get("machine_translation_used") is not False or entry.get("ai_rewriting_or_correction_used") is not False:
            errors.append(f"{key}: forbidden transformation flags changed")
        if str(entry.get("file") or "").startswith("/") or ".." in Path(str(entry.get("file") or "")).parts:
            errors.append(f"{key}: unsafe source path")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").is_file() else ""
    if "private_sources/" not in gitignore:
        errors.append("private_sources/ must be excluded from the public repository")
    if errors:
        raise SystemExit("All-services completion contract failed:\n- " + "\n- ".join(errors))
    print(f"ALL_SERVICES_COMPLETION_CONTRACT_OK exact={len(exact)}/45 source_files_required={len(incomplete)}")
    if args.production:
        subprocess.run([sys.executable, "scripts/validate_service_edition_evidence.py"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "scripts/validate_religious_completeness.py"], cwd=ROOT, check=True)
        print("ALL_SERVICES_COMPLETION_PRODUCTION_OK 45/45")


if __name__ == "__main__":
    main()
