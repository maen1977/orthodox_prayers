#!/usr/bin/env python3
"""Atomically promote three reviewed native Liturgy candidates.

No candidate is promoted alone. All three language files must pass their source
contract and carry explicit ecclesiastical approval. The command intentionally
does not update static hashes or sign release data; those remain separate human
review and release steps.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
CONTRACT = ROOT / "canonical/liturgy_native_import_contracts.json"
EDITIONS = ROOT / "canonical/liturgy_service_editions.json"


def candidate_hash(payload: dict[str, Any]) -> str:
    clone = copy.deepcopy(payload)
    clone.setdefault("ecclesiastical_review", {})["candidate_sha256"] = ""
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_candidate(payload: dict[str, Any], service: str, language: str, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    service_contract = contract["services"][service]
    lane = service_contract["lanes"][language]
    if payload.get("status") != "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW":
        errors.append(f"{language}: invalid candidate status")
    if payload.get("service_type") != service or payload.get("language") != language:
        errors.append(f"{language}: service/language mismatch")
    if payload.get("service_id") != service_contract["service_id"]:
        errors.append(f"{language}: service ID mismatch")
    if payload.get("machine_translation_used") is not False or payload.get("ai_rewriting_or_correction_used") is not False:
        errors.append(f"{language}: forbidden translation or AI rewriting flag")
    source = payload.get("source") or {}
    if source.get("source_id") != lane.get("source_id"):
        errors.append(f"{language}: source ID outside lane contract")
    health = payload.get("extraction_health") or {}
    if health.get("acceptable_candidate_extraction") is not True or health.get("failures"):
        errors.append(f"{language}: extraction health did not pass")
    review = payload.get("ecclesiastical_review") or {}
    if review.get("status") != "APPROVED":
        errors.append(f"{language}: ecclesiastical review is not APPROVED")
    if not str(review.get("reviewer") or "").strip() or not str(review.get("reviewed_at") or "").strip():
        errors.append(f"{language}: reviewer and reviewed_at are required")
    if review.get("source_page_verification") is not True:
        errors.append(f"{language}: page/paragraph source verification is required")
    expected_hash = candidate_hash(payload)
    if review.get("candidate_sha256") != expected_hash:
        errors.append(f"{language}: candidate hash mismatch after review")
    service_payload = payload.get("service") or {}
    segments = service_payload.get("segments") or []
    if len(segments) < int(service_contract["minimum_segments"][language]):
        errors.append(f"{language}: too few reviewed segments")
    return errors


def load_candidates(service: str, candidate_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    candidates: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for language in LANGS:
        path = candidate_dir / f"{language}.json"
        if not path.is_file():
            errors.append(f"missing candidate: {path}")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        candidates[language] = payload
        errors.extend(validate_candidate(payload, service, language, contract))
    if errors:
        raise RuntimeError("\n".join(errors))
    return candidates, contract


def apply_promotion(service: str, candidates: dict[str, dict[str, Any]], contract: dict[str, Any]) -> None:
    service_id = contract["services"][service]["service_id"]
    for language, candidate in candidates.items():
        for root in (ROOT / "data/services/native", ROOT / "app/src/main/assets/data/native"):
            path = root / f"library_{language}.json"
            pack = json.loads(path.read_text(encoding="utf-8"))
            services = [item for item in pack.get("services", []) if item.get("id") != service_id]
            promoted = copy.deepcopy(candidate["service"])
            promoted["native_source"]["import_status"] = "APPROVED_COMPLETE_NATIVE_EDITION"
            promoted["ecclesiastical_review"] = copy.deepcopy(candidate["ecclesiastical_review"])
            services.append(promoted)
            pack["services"] = services
            path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    editions = json.loads(EDITIONS.read_text(encoding="utf-8"))
    edition = editions["editions"][service]
    for language in LANGS:
        edition[language] = "IMPORTED_COMPLETE_NATIVE_EDITION_ECCLESIASTICALLY_APPROVED"
    edition["displayable"] = True
    edition["promoted_at"] = date.today().isoformat()
    editions["status"] = "NATIVE_SERVICE_EDITIONS_PROMOTED_REQUIRES_HASH_AND_RELEASE_SIGNATURE_REVIEW"
    EDITIONS.write_text(json.dumps(editions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True, choices=("basil", "presanctified"))
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    candidate_dir = args.candidate_dir or ROOT / "data/services/candidates" / args.service
    try:
        candidates, contract = load_candidates(args.service, candidate_dir)
    except Exception as exc:
        raise SystemExit(str(exc))
    if args.apply:
        apply_promotion(args.service, candidates, contract)
        mode = "applied"
    else:
        mode = "validated-only"
    print(f"NATIVE_LITURGY_PROMOTION_GATE_OK service={args.service} languages=3 mode={mode} static_hash_and_signature_review_required=true")


if __name__ == "__main__":
    main()
