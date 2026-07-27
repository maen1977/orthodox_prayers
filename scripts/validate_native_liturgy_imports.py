#!/usr/bin/env python3
"""Validate phase-seven native Liturgy acquisition and promotion gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "canonical/liturgy_native_import_contracts.json"
EVIDENCE_PATH = ROOT / "canonical/source_evidence/presanctified_ar_2018.json"
EDITIONS_PATH = ROOT / "canonical/liturgy_service_editions.json"
LANGS = ("ar", "en", "el")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Native Liturgy import validation failed: " + message)


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    editions = json.loads(EDITIONS_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    rules = contract.get("global_rules") or {}
    require(rules.get("all_published_languages_required") is True, "all three languages must be atomic")
    require(rules.get("machine_translation_allowed") is False, "machine translation must be disabled")
    require(rules.get("ai_rewriting_or_correction_allowed") is False, "AI correction must be disabled")
    require(rules.get("automatic_ocr_publication_allowed") is False, "OCR may not publish automatically")
    require(rules.get("ecclesiastical_human_review_required") is True, "human ecclesiastical review is required")
    require(rules.get("candidate_is_never_displayable") is True, "candidates must never be displayable")
    require(editions.get("wrong_liturgy_fallback_allowed") is False, "wrong-rite fallback must remain disabled")

    allowed_hosts = {
        "orthodoxjordan.org",
        "digitalchantstand.goarch.org",
        "dcs.goarch.org",
    }
    for service in ("basil", "presanctified"):
        service_contract = contract["services"][service]
        require(service_contract.get("service_id") == editions["editions"][service].get("service_id"), f"{service}: service ID mismatch")
        require(editions["editions"][service].get("displayable") is False, f"{service}: must stay blocked")
        for language in LANGS:
            lane = service_contract["lanes"][language]
            require(str(lane.get("status") or ""), f"{service}.{language}: missing lane status")
            url = str(lane.get("official_url") or "")
            require(urlparse(url).hostname in allowed_hosts, f"{service}.{language}: unapproved official domain")
            require(len(lane.get("anchors") or []) >= 3, f"{service}.{language}: insufficient verification anchors")
        require((ROOT / editions["editions"][service]["import_contract"]).is_file(), f"{service}: missing import contract")

    require(evidence.get("source_file_sha256") == "ace55aed85ca4ac9437bae5e7d3ebe2baab1a7cf4480c481602a64425077907e", "Arabic PDF source hash changed")
    require(evidence.get("pdf_pages") == 152, "Arabic PDF page count evidence")
    probe = evidence.get("text_extraction_probe") or {}
    require(probe.get("unicode_replacement_characters", 0) > 1000, "legacy-font corruption was not recorded")
    require(probe.get("acceptable_for_liturgical_publication") is False, "corrupt extraction must be blocked")
    require(probe.get("normalization_or_guessing_forbidden") is True, "heuristic repair must be forbidden")
    require(evidence.get("local_source_in_repository") is False, "copyrighted source PDF must remain external")

    # No unreviewed Basil or Presanctified service may be present in runtime packs.
    forbidden_ids = {"divine_liturgy_basil", "presanctified_liturgy"}
    for language in LANGS:
        for relative in (f"data/services/native/library_{language}.json", f"app/src/main/assets/data/native/library_{language}.json"):
            payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            ids = {str(item.get("id") or "") for item in payload.get("services") or []}
            require(not (ids & forbidden_ids), f"{relative}: unreviewed native service leaked into runtime")

    candidate_root = ROOT / "data/services/candidates"
    require((candidate_root / "README_AR.md").is_file(), "candidate review instructions missing")
    leaked = [path for path in candidate_root.rglob("*.json")]
    require(not leaked, "unreviewed candidate JSON must not ship in this phase")

    print("NATIVE_LITURGY_IMPORT_GATE_OK services=2 languages=3 candidates_displayable=false arabic_pdf_extraction=blocked runtime_leaks=0")


if __name__ == "__main__":
    main()
