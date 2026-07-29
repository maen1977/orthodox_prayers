#!/usr/bin/env python3
"""Validate source-backed evidence for services declared complete native editions."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "canonical/religious_completeness_manifest.json"
EVIDENCE_PATH = ROOT / "canonical/service_edition_evidence.json"
PACK_DIR = ROOT / "data/services/native"
LANGS = ("ar", "en", "el")
DEFAULT_COMPLETE = {"complete_exact_native_edition"}
AR = re.compile(r"[\u0600-\u06ff]")
EL = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")


def iter_localized(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("editorial_metadata_only") is True:
            return
        if any(k in value for k in LANGS):
            yield value
        else:
            for child in value.values():
                yield from iter_localized(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_localized(child)


def digest_text(service: dict[str, Any], lang: str) -> str:
    pieces = [str(obj.get(lang) or "").strip() for obj in iter_localized(service)]
    return hashlib.sha256("\n".join(x for x in pieces if x).encode("utf-8")).hexdigest()


def visible_text(service: dict[str, Any], lang: str) -> str:
    chunks: list[str] = []
    for segment in service.get("segments", []):
        if not isinstance(segment, dict):
            continue
        if segment.get("editorial_metadata_only") is True:
            continue
        for key in ("title", "speaker", "text"):
            value = segment.get(key)
            if isinstance(value, dict):
                text = str(value.get(lang) or "").strip()
                if text:
                    chunks.append(text)
    return "\n".join(chunks)


def section_titles(service: dict[str, Any], lang: str) -> list[str]:
    result: list[str] = []
    for segment in service.get("segments", []):
        if isinstance(segment, dict) and segment.get("type") == "section":
            title = str((segment.get("title") or {}).get(lang) or "").strip()
            if title:
                result.append(title)
    return result


def collect_errors() -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    if evidence.get("machine_translation_allowed") is not False:
        errors.append("service edition evidence must forbid machine translation")
    entries = evidence.get("services") if isinstance(evidence.get("services"), dict) else {}
    complete_statuses = set(manifest.get("production_complete_statuses") or DEFAULT_COMPLETE)
    packs: dict[str, dict[str, dict[str, Any]]] = {}
    for lang in LANGS:
        pack = json.loads((PACK_DIR / f"library_{lang}.json").read_text(encoding="utf-8"))
        packs[lang] = {str(s.get("id")): s for s in pack.get("services", []) if isinstance(s, dict)}

    for lang in LANGS:
        statuses = manifest["languages"][lang]
        for service_name, status in statuses.items():
            if status not in complete_statuses:
                continue
            packaged_id = manifest["packaged_service_ids"].get(service_name)
            service = packs[lang].get(str(packaged_id))
            key = f"{service_name}:{lang}"
            proof = entries.get(key)
            if not packaged_id or not service:
                errors.append(f"{key}: complete status has no packaged service")
                continue
            if not isinstance(proof, dict):
                errors.append(f"{key}: missing source-backed evidence")
                continue
            if proof.get("status") != status:
                errors.append(f"{key}: evidence status does not match manifest status")
            source = service.get("native_source") if isinstance(service.get("native_source"), dict) else {}
            if proof.get("source_id") != source.get("source_id"):
                errors.append(f"{key}: source id mismatch")
            if source.get("official") is not True:
                errors.append(f"{key}: source is not recorded as an official native-language publisher")
            if status == "complete_exact_native_edition" and source.get("permission_confirmed") is not True:
                errors.append(f"{key}: exact edition lacks recorded redistribution permission")
            if status == "complete_native_source_compilation" and source.get("permission_confirmed") is not True and source.get("redistribution_review_required") is not True:
                errors.append(f"{key}: compilation must record permission or require redistribution review")
            if source.get("machine_translation_used") is not False:
                errors.append(f"{key}: machine translation flag is invalid")
            actual_hash = digest_text(service, lang)
            if proof.get("content_sha256") != actual_hash or source.get("content_sha256") != actual_hash:
                errors.append(f"{key}: content hash mismatch")
            segments = service.get("segments") if isinstance(service.get("segments"), list) else []
            text = visible_text(service, lang)
            if len(segments) < int(proof.get("minimum_segments", 1)):
                errors.append(f"{key}: segment count below evidence minimum")
            if len(text) < int(proof.get("minimum_characters", 1)):
                errors.append(f"{key}: character count below evidence minimum")
            titles = "\n".join(section_titles(service, lang)).casefold()
            for checkpoint in proof.get("required_section_markers", []):
                if str(checkpoint).casefold() not in titles:
                    errors.append(f"{key}: missing required section marker {checkpoint!r}")
            folded_text = re.sub(r"\s+", " ", text.casefold()).strip()
            for checkpoint in proof.get("required_text_markers", []):
                marker = re.sub(r"\s+", " ", str(checkpoint).casefold()).strip()
                if marker and marker not in folded_text:
                    errors.append(f"{key}: missing required text marker {checkpoint!r}")
            for pattern in proof.get("forbidden_text_patterns", []):
                if re.search(str(pattern), text, flags=re.IGNORECASE):
                    errors.append(f"{key}: forbidden placeholder pattern {pattern!r}")
            if lang == "en" and (AR.search(text) or EL.search(text)):
                errors.append(f"{key}: non-English script leakage")
            if lang == "el" and AR.search(text):
                errors.append(f"{key}: Arabic script leakage")
            if lang == "ar" and EL.search(text):
                errors.append(f"{key}: Greek script leakage")
            doc = service.get("source_document") if isinstance(service.get("source_document"), dict) else {}
            expected_doc_hash = proof.get("source_snapshot_sha256")
            if expected_doc_hash and doc.get("document_sha256") != expected_doc_hash:
                errors.append(f"{key}: source snapshot hash mismatch")
    return errors


def main() -> None:
    errors = collect_errors()
    if errors:
        raise SystemExit("Service edition evidence validation failed:\n- " + "\n- ".join(errors))
    print("SERVICE_EDITION_EVIDENCE_OK")


if __name__ == "__main__":
    main()
