#!/usr/bin/env python3
"""Create a paragraph-by-paragraph ecclesiastical review packet.

The packet is external review material. It never promotes a candidate and must
not be copied into Android assets or committed with unreviewed source text.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def candidate_hash(payload: dict[str, Any]) -> str:
    clone = copy.deepcopy(payload)
    clone.setdefault("ecclesiastical_review", {})["candidate_sha256"] = ""
    return sha256_json(clone)


def segment_hash(segment: dict[str, Any]) -> str:
    stable = {
        "type": segment.get("type"),
        "speaker": segment.get("speaker") or {},
        "text": segment.get("text") or {},
        "title": segment.get("title") or {},
        "source_paragraph": segment.get("source_paragraph"),
    }
    return sha256_json(stable)


def build_packet(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("status") != "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW":
        raise ValueError("input is not a native-service review candidate")
    service = candidate.get("service") or {}
    segments = service.get("segments") or []
    if not isinstance(segments, list) or not segments:
        raise ValueError("candidate has no segments")
    language = str(candidate.get("language") or "")
    reviews = []
    for index, segment in enumerate(segments, start=1):
        localized_text = (segment.get("text") or {}).get(language) or (segment.get("title") or {}).get(language) or ""
        localized_speaker = (segment.get("speaker") or {}).get(language) or ""
        reviews.append({
            "index": index,
            "source_paragraph": segment.get("source_paragraph") or index,
            "segment_sha256": segment_hash(segment),
            "speaker": localized_speaker,
            "text": localized_text,
            "decision": "PENDING",
            "reviewer_note": ""
        })
    packet = {
        "schema_version": 1,
        "status": "REVIEW_PACKET_PENDING",
        "service_type": candidate.get("service_type"),
        "service_id": candidate.get("service_id"),
        "language": language,
        "candidate_sha256_before_review": candidate_hash(candidate),
        "source": copy.deepcopy(candidate.get("source") or {}),
        "review_policy": {
            "compare_every_segment_with_official_source": True,
            "translation_or_rewriting_forbidden": True,
            "all_decisions_must_be_APPROVED": True,
            "reviewer_identity_required": True,
            "reviewed_at_required": True
        },
        "reviewer": "",
        "reviewed_at": "",
        "attestation": "",
        "segment_reviews": reviews,
    }
    packet["packet_sha256"] = sha256_json({**packet, "packet_sha256": ""})
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    packet = build_packet(candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"NATIVE_LITURGY_REVIEW_PACKET_OK segments={len(packet['segment_reviews'])} output={args.output}")


if __name__ == "__main__":
    main()
