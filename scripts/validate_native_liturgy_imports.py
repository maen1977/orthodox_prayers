#!/usr/bin/env python3
"""Validate the authorized native Basil and Presanctified imports."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Native Liturgy import validation failed: " + message)


def visible_stats(service: dict, language: str) -> tuple[int, int]:
    count = 0
    characters = 0
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict) or segment.get("editorial_metadata_only") is True:
            continue
        value = segment.get("title") if segment.get("type") == "section" else segment.get("text")
        text = str(value.get(language) or "") if isinstance(value, dict) else ""
        if text.strip():
            count += 1
            characters += len(text)
    return count, characters


def main() -> None:
    contract = load("canonical/liturgy_native_import_contracts.json")
    editions = load("canonical/liturgy_service_editions.json")
    evidence = load("canonical/source_evidence/r66_authorized_liturgy_sources.json")
    authorization = load("canonical/owner_source_authorization.json")
    completeness = load("canonical/religious_completeness_manifest.json")
    rules = contract.get("global_rules") or {}

    require(authorization.get("status") == "CONFIRMED_BY_PROJECT_OWNER", "owner authorization is missing")
    require(rules.get("all_published_languages_required") is True, "all three languages must remain atomic")
    require(rules.get("machine_translation_allowed") is False, "machine translation must be disabled")
    require(rules.get("ai_rewriting_or_correction_allowed") is False, "AI rewriting must be disabled")
    require(rules.get("ecclesiastical_human_certification_claimed") is False, "human ecclesiastical certification must not be fabricated")
    require(editions.get("wrong_liturgy_fallback_allowed") is False, "wrong-rite fallback must remain disabled")
    require(evidence.get("policy") == "SOURCE_LETTERS_ONLY_NO_TRANSLATION_NO_AI_REWRITING", "R66 extraction policy mismatch")
    require(evidence.get("ecclesiastical_human_certification") == "NOT_CLAIMED", "R66 review claim mismatch")
    for evidence_key in ("orthros_ar", "basil_ar", "basil_el", "presanctified_ar"):
        item = evidence.get(evidence_key) or {}
        require(item.get("source_sha256"), f"{evidence_key}: source hash missing")
        require(all((item.get("anchors") or {}).values()), f"{evidence_key}: required anchor missing")

    allowed_hosts = {
        "orthodoxjordan.org", "digitalchantstand.goarch.org", "dcs.goarch.org",
        "saintgeorgeflint.org", "www.stgeorgeramallah.org",
    }
    complete_statuses = set(completeness.get("production_complete_statuses") or [])
    minimums = {
        ("basil", "ar"): (150, 20000), ("basil", "en"): (90, 18000), ("basil", "el"): (150, 28000),
        ("presanctified", "ar"): (1000, 100000), ("presanctified", "en"): (90, 18000), ("presanctified", "el"): (90, 18000),
    }
    for service_name, manifest_name in (("basil", "basil_liturgy"), ("presanctified", "presanctified_liturgy")):
        edition = editions["editions"][service_name]
        require(edition.get("displayable") is True, f"{service_name}: complete rite is not displayable")
        require(edition.get("ecclesiastical_human_certification") == "NOT_CLAIMED", f"{service_name}: invalid ecclesiastical claim")
        for language in LANGS:
            lane = contract["services"][service_name]["lanes"][language]
            require(urlparse(str(lane.get("official_url") or "")).hostname in allowed_hosts, f"{service_name}.{language}: unapproved source domain")
            require(completeness["languages"][language][manifest_name] in complete_statuses, f"{service_name}.{language}: incomplete manifest lane")
            pack = load(f"data/services/native/library_{language}.json")
            service = next((item for item in pack.get("services") or [] if item.get("id") == edition["service_id"]), None)
            require(isinstance(service, dict), f"{service_name}.{language}: native service missing")
            count, characters = visible_stats(service, language)
            minimum_count, minimum_characters = minimums[(service_name, language)]
            require(count >= minimum_count and characters >= minimum_characters, f"{service_name}.{language}: service below complete-text threshold")

    leaked = list((ROOT / "data/services/candidates").rglob("*.json"))
    require(not leaked, "unreviewed candidate JSON must not ship")
    print("NATIVE_LITURGY_IMPORT_GATE_OK services=2 languages=3 displayable=true owner_authorized=true machine_translation=false ecclesiastical_certification=false")


if __name__ == "__main__":
    main()
