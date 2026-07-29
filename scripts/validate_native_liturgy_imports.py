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

    # Recovered exact native editions may be stored lane-by-lane, while the
    # cross-language service remains fail-closed until all three lanes exist.
    completeness = json.loads(
        (ROOT / "canonical/religious_completeness_manifest.json").read_text(encoding="utf-8")
    )
    edition_evidence = json.loads(
        (ROOT / "canonical/service_edition_evidence.json").read_text(encoding="utf-8")
    )
    complete = completeness["production_complete_status"]
    production_complete_statuses = set(completeness.get("production_complete_statuses") or [complete])
    compilation_status = "complete_native_source_compilation"
    expected_exact = {
        ("ar", "presanctified_liturgy", "presanctified_liturgy"),
        ("en", "basil_liturgy", "divine_liturgy_basil"),
        ("el", "basil_liturgy", "divine_liturgy_basil"),
        ("en", "presanctified_liturgy", "presanctified_liturgy"),
        ("el", "presanctified_liturgy", "presanctified_liturgy"),
    }
    exact_recovery_statuses = {
        "RECOVERED_EXACT_NATIVE_IMPORT",
        "PUBLIC_DOMAIN_EXACT_NATIVE_IMPORT",
    }
    for language in LANGS:
        for relative in (
            f"data/services/native/library_{language}.json",
            f"app/src/main/assets/data/native/library_{language}.json",
        ):
            payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            service_map = {
                str(item.get("id") or ""): item
                for item in payload.get("services") or []
                if isinstance(item, dict)
            }
            for service_name, service_id in (
                ("basil_liturgy", "divine_liturgy_basil"),
                ("presanctified_liturgy", "presanctified_liturgy"),
            ):
                require(service_id in service_map, f"{relative}: missing service shell {service_id}")
                item = service_map[service_id]
                declared_status = completeness["languages"][language][service_name]
                lane_is_exact = (language, service_name, service_id) in expected_exact
                require((declared_status == complete) is lane_is_exact, f"{service_name}.{language}: exact completeness mismatch")
                recovery_status = str(item.get("recovery_status") or "")
                evidence_key = f"{service_name}:{language}"
                proof = edition_evidence.get("services", {}).get(evidence_key)
                if lane_is_exact:
                    require(
                        recovery_status in exact_recovery_statuses,
                        f"{service_name}.{language}: exact recovery marker missing",
                    )
                    require(isinstance(proof, dict), f"{evidence_key}: exact evidence missing")
                    require(proof.get("status") == complete, f"{evidence_key}: exact evidence status mismatch")
                    minimum_segments = int(proof.get("minimum_segments", 1))
                    require(
                        len(item.get("segments") or []) >= minimum_segments,
                        f"{service_name}.{language}: segment count below evidence minimum",
                    )
                elif declared_status == compilation_status:
                    require(
                        recovery_status not in exact_recovery_statuses,
                        f"{service_name}.{language}: compilation falsely marked as an exact recovery",
                    )
                    require(isinstance(proof, dict), f"{evidence_key}: compilation evidence missing")
                    require(proof.get("status") == compilation_status, f"{evidence_key}: compilation evidence status mismatch")
                    minimum_segments = int(proof.get("minimum_segments", 1))
                    require(
                        len(item.get("segments") or []) >= minimum_segments,
                        f"{service_name}.{language}: compilation segment count below evidence minimum",
                    )
                else:
                    require(declared_status not in production_complete_statuses, f"{service_name}.{language}: unsupported complete status")
                    require(
                        recovery_status not in exact_recovery_statuses,
                        f"{service_name}.{language}: unapproved exact marker",
                    )
                    require(
                        all(
                            segment.get("editorial_metadata_only") is True
                            for segment in item.get("segments") or []
                        ),
                        f"{service_name}.{language}: unreviewed liturgical text leaked",
                    )

    candidate_root = ROOT / "data/services/candidates"
    require((candidate_root / "README_AR.md").is_file(), "candidate review instructions missing")
    leaked = [path for path in candidate_root.rglob("*.json")]
    require(not leaked, "unreviewed candidate JSON must not ship in this phase")

    print("NATIVE_LITURGY_IMPORT_GATE_OK services=2 languages=3 exact_native_lanes=5 overall_displayable=false arabic_pdf_extraction=blocked")


if __name__ == "__main__":
    main()
