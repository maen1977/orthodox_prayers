#!/usr/bin/env python3
"""Verify pinned core-prayer text and truthful completeness declarations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "canonical/static_prayer_sources.json"
LIBRARIES = [ROOT / "app/src/main/assets/data/library.json", ROOT / "data/services/library.json"]
REQUIRED = {"lord_prayer", "creed", "trisagion", "before_food", "after_food"}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["services"]
    if set(registry) != REQUIRED:
        raise SystemExit("static prayer registry must contain exactly the required core prayer ids")
    for service_id, record in registry.items():
        if record.get("source_id") != "orthodox_jordan" or record.get("priority") != 1:
            raise SystemExit(f"{service_id}: official Jordan priority evidence is missing")
        if record.get("status") != "OFFICIAL_ARABIC_EXACT_PINNED":
            raise SystemExit(f"{service_id}: exact pinned-source status is missing")
        if record.get("complete_text") not in (True, False):
            raise SystemExit(f"{service_id}: complete_text must be explicitly true or false")
        if record.get("complete_text") is False and not str(record.get("completeness_note_ar") or "").strip():
            raise SystemExit(f"{service_id}: incomplete text requires a truthful completeness note")
        if record.get("ai_translation_used") is not False:
            raise SystemExit(f"{service_id}: AI translation must be disabled")

    for path in LIBRARIES:
        data = json.loads(path.read_text(encoding="utf-8"))
        services = {item["id"]: item for item in data["services"]}
        for service_id, record in registry.items():
            service = services[service_id]
            provenance = service.get("source_provenance", {})
            if provenance.get("status") != "OFFICIAL_ARABIC_EXACT_PINNED":
                raise SystemExit(f"{path.name}:{service_id}: exact official provenance missing")
            ar = "\n".join(
                segment.get("text", {}).get("ar", "")
                for segment in service.get("segments", [])
                if segment.get("text", {}).get("ar")
            )
            if digest(ar) != record["arabic_sha256"]:
                raise SystemExit(f"{path.name}:{service_id}: Arabic text hash mismatch")
            if service_id == "creed":
                for clause in ("نُورٍ مِنْ نُورٍ", "وَصُلِبَ عَنَّا", "وَبِكَنِيسَةٍ وَاحِدَةٍ", "وَأَتَرَجَّى قِيَامَةَ الْمَوْتَى"):
                    if clause not in ar:
                        raise SystemExit(f"{path.name}: Creed is incomplete; missing {clause}")
            if service_id == "trisagion" and len(service.get("segments", [])) < 6:
                raise SystemExit(f"{path.name}: Trisagion sequence is incomplete")
    complete = sum(1 for record in registry.values() if record.get("complete_text") is True)
    incomplete = len(registry) - complete
    print(f"Pinned Orthodox Jordan prayer texts and hashes validated: {complete} complete, {incomplete} explicitly partial")


if __name__ == "__main__":
    main()
