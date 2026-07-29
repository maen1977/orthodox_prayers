#!/usr/bin/env python3
"""Apply a completed human review packet to a candidate, without promotion."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from build_native_liturgy_review_packet import candidate_hash, segment_hash

REQUIRED_ATTESTATION = "I compared every segment with the registered official source."


def validate_and_apply(candidate: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("status") != "REVIEW_PACKET_COMPLETED":
        errors.append("review packet status is not REVIEW_PACKET_COMPLETED")
    if packet.get("candidate_sha256_before_review") != candidate_hash(candidate):
        errors.append("candidate changed after packet creation")
    if packet.get("service_type") != candidate.get("service_type") or packet.get("language") != candidate.get("language"):
        errors.append("packet candidate identity mismatch")
    reviewer = str(packet.get("reviewer") or "").strip()
    reviewed_at = str(packet.get("reviewed_at") or "").strip()
    if not reviewer or not reviewed_at:
        errors.append("reviewer and reviewed_at are required")
    if str(packet.get("attestation") or "").strip() != REQUIRED_ATTESTATION:
        errors.append("exact review attestation is required")
    segments = (candidate.get("service") or {}).get("segments") or []
    reviews = packet.get("segment_reviews") or []
    if len(segments) != len(reviews):
        errors.append("review count does not match candidate segments")
    else:
        for index, (segment, review) in enumerate(zip(segments, reviews), start=1):
            if review.get("index") != index:
                errors.append(f"segment {index}: index mismatch")
            if review.get("segment_sha256") != segment_hash(segment):
                errors.append(f"segment {index}: hash mismatch")
            if review.get("decision") != "APPROVED":
                errors.append(f"segment {index}: not APPROVED")
    if errors:
        raise RuntimeError("\n".join(errors))
    reviewed = copy.deepcopy(candidate)
    review = reviewed.setdefault("ecclesiastical_review", {})
    review.update({
        "status": "APPROVED",
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "source_page_verification": True,
        "review_packet_sha256": hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "candidate_sha256": "",
    })
    review["candidate_sha256"] = candidate_hash(reviewed)
    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    reviewed = validate_and_apply(candidate, packet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"NATIVE_LITURGY_REVIEW_APPLIED_OK language={reviewed['language']} promotion=false output={args.output}")


if __name__ == "__main__":
    main()
