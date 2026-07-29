#!/usr/bin/env python3
"""Prepare every incomplete service-language lane in one fail-closed round.

The command reads authorized source files from a private directory, validates
same-language extraction and provenance, then writes non-displayable candidates
and paragraph review packets. It never modifies runtime assets or completeness
claims. Production promotion is a separate all-or-nothing command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_native_liturgy_review_packet import build_packet, candidate_hash  # noqa: E402
from import_native_liturgy_service import extract_source, localized  # noqa: E402
from validate_service_edition_evidence import collect_errors as evidence_errors  # noqa: E402

CONTRACT_PATH = ROOT / "canonical/all_services_completion_round.json"
LANGS = ("ar", "en", "el")
ALLOWED_SOURCE_HOSTS = {
    "orthodoxjordan.org",
    "www.orthodoxjordan.org",
    "digitalchantstand.goarch.org",
    "dcs.goarch.org",
    "goarchdiocese.ca",
    "www.goarchdiocese.ca",
    "www.goarch.org",
    "goarch.org",
    "apostoliki-diakonia.gr",
    "www.apostoliki-diakonia.gr",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fold(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def script_class(char: str) -> str:
    name = unicodedata.name(char, "")
    if "ARABIC" in name:
        return "Arabic"
    if "GREEK" in name:
        return "Greek"
    if "LATIN" in name:
        return "Latin"
    return "Other"


def source_host(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").casefold()


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [
        re.sub(r"[ \t]+", " ", item).strip()
        for item in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
        if item.strip()
    ]
    # Some HTML/text exports use one newline per paragraph. Preserve long lines
    # as separate review units when double-newline splitting yields too little.
    if len(paragraphs) < 8:
        lines = [re.sub(r"[ \t]+", " ", item).strip() for item in text.splitlines() if item.strip()]
        if len(lines) > len(paragraphs):
            paragraphs = lines
    return paragraphs


def analyze(text: str, lane: dict[str, Any]) -> dict[str, Any]:
    language = str(lane["language"])
    letters = [ch for ch in text if ch.isalpha()]
    expected = {"ar": "Arabic", "en": "Latin", "el": "Greek"}[language]
    counts = {name: sum(script_class(ch) == name for ch in letters) for name in ("Arabic", "Latin", "Greek")}
    expected_ratio = counts[expected] / max(1, len(letters))
    paragraphs = split_paragraphs(text)
    folded = fold(text)
    anchors = [str(item) for item in lane.get("anchors") or []]
    found = [item for item in anchors if fold(item) in folded]
    failures: list[str] = []
    replacement = text.count("\ufffd")
    controls = sum(unicodedata.category(ch) == "Cc" and ch not in "\n\r\t" for ch in text)
    if replacement:
        failures.append(f"UNICODE_REPLACEMENT_CHARACTERS={replacement}")
    if controls:
        failures.append(f"UNSAFE_CONTROL_CHARACTERS={controls}")
    if expected_ratio < 0.72:
        failures.append(f"WRONG_SCRIPT_RATIO={expected_ratio:.4f}")
    if len(text.strip()) < int(lane["minimum_characters"]):
        failures.append(f"TEXT_TOO_SHORT={len(text.strip())}<{lane['minimum_characters']}")
    if len(paragraphs) < int(lane["minimum_paragraphs"]):
        failures.append(f"TOO_FEW_PARAGRAPHS={len(paragraphs)}<{lane['minimum_paragraphs']}")
    if len(found) < min(2, len(anchors)):
        failures.append(f"REQUIRED_ANCHORS_MISSING={len(found)}/{len(anchors)}")
    whitespace_ratio = sum(ch.isspace() for ch in text) / max(1, len(letters))
    if language == "ar" and len(letters) > 1000 and whitespace_ratio < 0.055:
        failures.append(f"ARABIC_WORD_BOUNDARIES_CORRUPTED={whitespace_ratio:.4f}")
    forbidden = ("placeholder", "todo", "text to be added", "يضاف لاحقا", "يضاف لاحقاً", "نص مؤقت")
    for marker in forbidden:
        if marker.casefold() in text.casefold():
            failures.append(f"FORBIDDEN_PLACEHOLDER={marker}")
    return {
        "characters": len(text),
        "paragraph_count": len(paragraphs),
        "script_counts": counts,
        "expected_script": expected,
        "expected_script_ratio": round(expected_ratio, 6),
        "unicode_replacement_characters": replacement,
        "unsafe_control_characters": controls,
        "whitespace_to_letter_ratio": round(whitespace_ratio, 6),
        "anchors_required": anchors,
        "anchors_found": found,
        "acceptable_candidate_extraction": not failures,
        "failures": failures,
    }


def _visible_language_text(value: Any, language: str) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            text = str(value.get(language) or "").strip()
            if text:
                result.append(text)
        else:
            for child in value.values():
                result.extend(_visible_language_text(child, language))
    elif isinstance(value, list):
        for child in value:
            result.extend(_visible_language_text(child, language))
    return result


def load_structured_service(path: Path, lane: dict[str, Any], raw_paragraphs: list[str]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    service = payload.get("service") if isinstance(payload.get("service"), dict) else payload
    if not isinstance(service, dict) or service.get("id") != lane["service_id"]:
        raise RuntimeError("normalized service JSON has the wrong service id")
    language = str(lane["language"])
    segments = service.get("segments")
    if not isinstance(segments, list) or not segments:
        raise RuntimeError("normalized service JSON has no segments")
    mapped = 0
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            raise RuntimeError(f"normalized segment {index} is not an object")
        # Other language lanes must remain empty in an independent native candidate.
        for localized_obj in (segment.get("title"), segment.get("speaker"), segment.get("text")):
            if not isinstance(localized_obj, dict):
                continue
            for other in LANGS:
                if other != language and str(localized_obj.get(other) or "").strip():
                    raise RuntimeError(f"normalized segment {index} leaks text into {other}")
        visible = " ".join(_visible_language_text({k: segment.get(k) for k in ("title", "speaker", "text")}, language)).strip()
        if not visible:
            if segment.get("editorial_metadata_only") is not True:
                raise RuntimeError(f"normalized segment {index} has no visible {language} text")
            continue
        source_paragraph = int(segment.get("source_paragraph") or 0)
        if source_paragraph < 1 or source_paragraph > len(raw_paragraphs):
            raise RuntimeError(f"normalized segment {index} has invalid source_paragraph")
        source_folded = fold(raw_paragraphs[source_paragraph - 1])
        # Compare the prayer/rubric text, not editor-added role labels. A normalized
        # visible string must retain a substantial exact phrase from its source paragraph.
        text_value = segment.get("text") if isinstance(segment.get("text"), dict) else {}
        title_value = segment.get("title") if isinstance(segment.get("title"), dict) else {}
        mapped_text = str(text_value.get(language) or title_value.get(language) or "").strip()
        if mapped_text:
            normalized_folded = fold(mapped_text)
            if normalized_folded not in source_folded and source_folded not in normalized_folded:
                raise RuntimeError(f"normalized segment {index} text does not map exactly to source paragraph {source_paragraph}")
        mapped += 1
    if mapped < int(lane["minimum_paragraphs"]):
        raise RuntimeError(f"normalized service maps too few segments: {mapped}<{lane['minimum_paragraphs']}")
    result = json.loads(json.dumps(service, ensure_ascii=False))
    result["source_language"] = language
    result["content_mode"] = "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY"
    return result


def build_candidate(lane_key: str, lane: dict[str, Any], source_meta: dict[str, Any], source_path: Path, normalized_path: Path | None) -> dict[str, Any]:
    text, source_format = extract_source(source_path)
    health = analyze(text, lane)
    if not health["acceptable_candidate_extraction"]:
        raise RuntimeError("; ".join(health["failures"]))
    language = str(lane["language"])
    title = str(source_meta.get("document_title") or "").strip()
    if not title:
        raise RuntimeError("document_title is required")
    paragraphs = split_paragraphs(text)
    structured_service = load_structured_service(normalized_path, lane, paragraphs) if normalized_path else None
    source_hash = sha256_bytes(source_path.read_bytes())
    declared_hash = str(source_meta.get("file_sha256") or "").strip().casefold()
    if not declared_hash:
        raise RuntimeError("file_sha256 is required")
    if declared_hash != source_hash:
        raise RuntimeError(f"file SHA-256 mismatch: declared={declared_hash} actual={source_hash}")
    if source_meta.get("official_source") is not True or source_meta.get("permission_confirmed") is not True:
        raise RuntimeError("official_source=true and permission_confirmed=true are required")
    if source_meta.get("machine_translation_used") is not False:
        raise RuntimeError("machine_translation_used must be false")
    if source_meta.get("ai_rewriting_or_correction_used") is not False:
        raise RuntimeError("ai_rewriting_or_correction_used must be false")
    source_id = str(source_meta.get("source_id") or "")
    if source_id != lane["source_id"]:
        raise RuntimeError(f"source_id must be {lane['source_id']}")
    source_url = str(source_meta.get("source_url") or "").strip()
    if source_host(source_url) not in ALLOWED_SOURCE_HOSTS:
        raise RuntimeError("source_url host is not in the official-source allowlist")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
        "completion_round": "ALL_SERVICES_V1",
        "lane_key": lane_key,
        "service_type": lane["service"],
        "service_id": lane["service_id"],
        "language": language,
        "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
        "machine_translation_used": False,
        "ai_rewriting_or_correction_used": False,
        "source": {
            "source_id": source_id,
            "url": source_url,
            "document_title": title,
            "format": source_format,
            "file_sha256": source_hash,
            "extracted_text_sha256": sha256_text(text),
            "private_source_file_not_packaged": True,
        },
        "extraction_health": health,
        "ecclesiastical_review": {
            "status": "PENDING",
            "reviewer": "",
            "reviewed_at": "",
            "source_page_verification": False,
            "candidate_sha256": "",
        },
        "structure_status": "STRUCTURED_EXACT_SOURCE_MAPPING" if structured_service else "FLAT_EXTRACTION_REQUIRES_STRUCTURING",
        "service": structured_service or {
            "id": lane["service_id"],
            "category": "liturgy" if "liturgy" in lane["service"] or lane["service"] == "proskomide" else "daily_office",
            "icon": "⛪",
            "title": localized(title, language),
            "summary": localized("", language),
            "source_language": language,
            "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
            "segments": [
                {
                    "type": "text",
                    "speaker": localized("", language),
                    "text": localized(paragraph, language),
                    "source_paragraph": index,
                }
                for index, paragraph in enumerate(paragraphs, start=1)
            ],
            "native_source": {
                "source_id": source_id,
                "url": source_url,
                "official": True,
                "native_language": language,
                "permission_confirmed": True,
                "machine_translation_used": False,
                "source_file_sha256": source_hash,
                "content_sha256": sha256_text(text),
                "import_status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
            },
        },
        "publication": {
            "displayable": False,
            "runtime_candidate_allowed": False,
            "partial_round_promotion_allowed": False,
        },
    }
    payload["service"]["native_source"] = {
        "source_id": source_id,
        "url": source_url,
        "official": True,
        "native_language": language,
        "permission_confirmed": True,
        "machine_translation_used": False,
        "source_file_sha256": source_hash,
        "content_sha256": sha256_text(text),
        "import_status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
    }
    payload["ecclesiastical_review"]["candidate_sha256"] = candidate_hash(payload)
    return payload


def safe_source_path(source_root: Path, relative: str) -> Path:
    candidate = (source_root / relative).resolve()
    root = source_root.resolve()
    if root != candidate and root not in candidate.parents:
        raise RuntimeError("source file escapes source bundle root")
    return candidate


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(source_root: Path, output_root: Path) -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    exact_errors = evidence_errors()
    if exact_errors:
        raise RuntimeError("current exact-edition evidence failed: " + "; ".join(exact_errors))
    manifest_path = source_root / "manifest.json"
    source_manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = source_manifest.get("entries") if isinstance(source_manifest.get("entries"), dict) else {}

    temp_parent = output_root.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=output_root.name + ".", dir=temp_parent))
    complete_current: list[str] = []
    prepared: list[str] = []
    missing: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    try:
        for lane_key, lane in contract["lanes"].items():
            if lane["already_release_ready"]:
                complete_current.append(lane_key)
                continue
            entry = entries.get(lane_key)
            if not isinstance(entry, dict):
                missing.append({"lane": lane_key, "reason": "manifest entry missing"})
                continue
            relative = str(entry.get("file") or "").strip()
            if not relative or relative.endswith(".EXT"):
                missing.append({"lane": lane_key, "reason": "source file path not configured"})
                continue
            try:
                source_path = safe_source_path(source_root, relative)
                if not source_path.is_file():
                    raise RuntimeError(f"source file missing: {relative}")
                if source_path.suffix.casefold() not in set(lane["accepted_extensions"]):
                    raise RuntimeError(f"unsupported source extension: {source_path.suffix}")
                normalized_relative = str(entry.get("normalized_service_file") or "").strip()
                normalized_path = safe_source_path(source_root, normalized_relative) if normalized_relative else None
                if normalized_path is not None and not normalized_path.is_file():
                    normalized_path = None
                payload = build_candidate(lane_key, lane, entry, source_path, normalized_path)
                candidate_path = temp_dir / "candidates" / lane["service"] / f"{lane['language']}.json"
                packet_path = temp_dir / "review_packets" / lane["service"] / f"{lane['language']}.json"
                write_json(candidate_path, payload)
                write_json(packet_path, build_packet(payload))
                prepared.append(lane_key)
            except Exception as exc:  # each lane is independently reported; runtime remains untouched
                rejected.append({"lane": lane_key, "reason": str(exc)})

        report = {
            "schema_version": 1,
            "status": "SOURCE_BUNDLE_READY_FOR_REVIEW" if not missing and not rejected else "SOURCE_BUNDLE_INCOMPLETE_FAIL_CLOSED",
            "runtime_modified": False,
            "total_lanes": contract["total_lanes"],
            "current_exact_lanes": len(complete_current),
            "new_source_lanes_required": len(contract["required_new_source_lanes"]),
            "candidates_prepared": len(prepared),
            "resolved_lanes": len(complete_current) + len(prepared),
            "missing_lanes": missing,
            "rejected_lanes": rejected,
            "prepared_lane_keys": prepared,
            "source_bundle_manifest_present": manifest_path.is_file(),
            "all_sources_ready": not missing and not rejected,
            "next_gate": "complete every generated paragraph review packet, then run promote_all_services_completion_round.py",
        }
        write_json(temp_dir / "audit.json", report)
        if output_root.exists():
            shutil.rmtree(output_root)
        os.replace(temp_dir, output_root)
        return report
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=ROOT / "private_sources/all_services_v1")
    parser.add_argument("--output-root", type=Path, default=ROOT / "build/all-services-completion-round")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = run(args.source_root.resolve(), args.output_root.resolve())
    print(
        "ALL_SERVICES_COMPLETION_ROUND "
        f"resolved={report['resolved_lanes']}/{report['total_lanes']} "
        f"prepared={report['candidates_prepared']} runtime_modified=false status={report['status']}"
    )
    if args.require_complete and not report["all_sources_ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
