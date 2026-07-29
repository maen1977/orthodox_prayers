#!/usr/bin/env python3
"""Build a non-displayable native Liturgy candidate from an exact official source.

This importer never translates, rewrites, corrects OCR, or promotes content. It
extracts same-language text, applies deterministic health gates, and writes a
candidate that still requires paragraph-by-paragraph ecclesiastical review.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "canonical/liturgy_native_import_contracts.json"
LANGS = ("ar", "en", "el")
SERVICES = ("basil", "presanctified")


class _HTMLText(HTMLParser):
    BREAK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        data = archive.read("word/document.xml")
    root = ET.fromstring(data)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag.endswith("}t") and node.text:
                parts.append(node.text)
            elif node.tag.endswith("}tab"):
                parts.append("\t")
            elif node.tag.endswith("}br") or node.tag.endswith("}cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_html(path: Path) -> str:
    parser = _HTMLText()
    parser.feed(path.read_text(encoding="utf-8", errors="strict"))
    return html.unescape("".join(parser.parts))


def extract_pdf(path: Path) -> str:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
        errors="replace",
    )
    return completed.stdout.replace("\f", "\n\n")


def extract_source(path: Path) -> tuple[str, str]:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        return extract_docx(path), "docx"
    if suffix in {".html", ".htm"}:
        return extract_html(path), "html"
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="strict"), "txt"
    if suffix == ".pdf":
        return extract_pdf(path), "pdf"
    raise ValueError(f"Unsupported source format: {suffix or '<none>'}")


def script_name(char: str) -> str:
    name = unicodedata.name(char, "")
    if "ARABIC" in name:
        return "Arabic"
    if "GREEK" in name:
        return "Greek"
    if "LATIN" in name:
        return "Latin"
    return "Other"


def _fold_anchor(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def analyze_text(text: str, language: str, lane_contract: dict[str, Any], service_contract: dict[str, Any]) -> dict[str, Any]:
    if language not in LANGS:
        raise ValueError(f"Unsupported language: {language}")
    letters = [ch for ch in text if ch.isalpha()]
    counts = {name: sum(script_name(ch) == name for ch in letters) for name in ("Arabic", "Greek", "Latin")}
    expected = {"ar": "Arabic", "el": "Greek", "en": "Latin"}[language]
    expected_ratio = counts[expected] / max(1, len(letters))
    replacement_count = text.count("\ufffd")
    null_count = text.count("\x00")
    control_count = sum(unicodedata.category(ch) == "Cc" and ch not in "\n\r\t" for ch in text)
    whitespace_ratio = sum(ch.isspace() for ch in text) / max(1, len(letters))
    folded = _fold_anchor(text)
    anchors = [str(item) for item in lane_contract.get("anchors") or []]
    anchors_found = [anchor for anchor in anchors if _fold_anchor(anchor) in folded]
    nonempty_paragraphs = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    min_chars = int((service_contract.get("minimum_characters") or {}).get(language, 0))
    min_segments = int((service_contract.get("minimum_segments") or {}).get(language, 0))
    failures: list[str] = []
    if replacement_count:
        failures.append(f"UNICODE_REPLACEMENT_CHARACTERS={replacement_count}")
    if null_count or control_count:
        failures.append(f"UNSAFE_CONTROL_CHARACTERS={null_count + control_count}")
    if expected_ratio < 0.82:
        failures.append(f"WRONG_SCRIPT_RATIO={expected_ratio:.4f}")
    if len(text.strip()) < min_chars:
        failures.append(f"TEXT_TOO_SHORT={len(text.strip())}<{min_chars}")
    if len(nonempty_paragraphs) < min_segments:
        failures.append(f"TOO_FEW_PARAGRAPHS={len(nonempty_paragraphs)}<{min_segments}")
    if anchors and len(anchors_found) < min(2, len(anchors)):
        failures.append(f"REQUIRED_ANCHORS_MISSING={len(anchors_found)}/{len(anchors)}")
    # A long Arabic extraction with almost no word boundaries is a known symptom
    # of legacy custom-font decoding. Never repair it heuristically.
    if language == "ar" and len(letters) > 1000 and whitespace_ratio < 0.055:
        failures.append(f"ARABIC_WORD_BOUNDARIES_CORRUPTED={whitespace_ratio:.4f}")
    return {
        "characters": len(text),
        "letters": len(letters),
        "script_counts": counts,
        "expected_script": expected,
        "expected_script_ratio": round(expected_ratio, 6),
        "unicode_replacement_characters": replacement_count,
        "unsafe_control_characters": null_count + control_count,
        "whitespace_to_letter_ratio": round(whitespace_ratio, 6),
        "paragraph_count": len(nonempty_paragraphs),
        "minimum_characters": min_chars,
        "minimum_segments": min_segments,
        "anchors_required": anchors,
        "anchors_found": anchors_found,
        "acceptable_candidate_extraction": not failures,
        "failures": failures,
    }


def localized(value: str, language: str) -> dict[str, str]:
    return {lang: value if lang == language else "" for lang in LANGS}


def candidate_segments(text: str, language: str) -> list[dict[str, Any]]:
    paragraphs = [re.sub(r"[ \t]+", " ", item).strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    return [
        {
            "type": "text",
            "speaker": localized("", language),
            "text": localized(paragraph, language),
            "source_paragraph": index + 1,
        }
        for index, paragraph in enumerate(paragraphs)
    ]


def load_contract(service: str, language: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    service_contract = (root.get("services") or {}).get(service)
    if not isinstance(service_contract, dict):
        raise ValueError(f"Unknown service contract: {service}")
    lane = (service_contract.get("lanes") or {}).get(language)
    if not isinstance(lane, dict):
        raise ValueError(f"Missing {service}.{language} lane contract")
    return root, service_contract, lane


def build_candidate(
    *, service: str, language: str, source: Path, source_id: str, source_url: str,
    document_title: str,
) -> dict[str, Any]:
    root_contract, service_contract, lane = load_contract(service, language)
    if source_id != lane.get("source_id"):
        raise ValueError(f"Source ID must match contract: {lane.get('source_id')}")
    text, source_format = extract_source(source)
    health = analyze_text(text, language, lane, service_contract)
    if not health["acceptable_candidate_extraction"]:
        raise RuntimeError("Unsafe native source extraction: " + "; ".join(health["failures"]))
    source_bytes = source.read_bytes()
    service_id = str(service_contract["service_id"])
    payload = {
        "schema_version": 1,
        "status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
        "service_type": service,
        "service_id": service_id,
        "language": language,
        "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
        "machine_translation_used": False,
        "ai_rewriting_or_correction_used": False,
        "source": {
            "source_id": source_id,
            "url": source_url,
            "document_title": document_title,
            "format": source_format,
            "file_sha256": sha256_bytes(source_bytes),
            "extracted_text_sha256": sha256_text(text),
        },
        "extraction_health": health,
        "ecclesiastical_review": {
            "status": "PENDING",
            "reviewer": "",
            "reviewed_at": "",
            "source_page_verification": False,
            "candidate_sha256": "",
        },
        "service": {
            "id": service_id,
            "category": "liturgy",
            "icon": "⛪",
            "title": localized(document_title, language),
            "summary": localized("", language),
            "source_language": language,
            "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
            "segments": candidate_segments(text, language),
            "native_source": {
                "source_id": source_id,
                "url": source_url,
                "official": True,
                "native_language": language,
                "machine_translation_used": False,
                "source_file_sha256": sha256_bytes(source_bytes),
                "content_sha256": sha256_text(text),
                "import_status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
            },
        },
        "publication": {
            "displayable": False,
            "runtime_candidate_allowed": False,
            "wrong_liturgy_fallback_allowed": False,
            "promotion_requires_all_languages": list(root_contract["languages"]),
        },
    }
    # Candidate hash excludes the review field that will later contain the hash.
    hash_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    hash_payload["ecclesiastical_review"]["candidate_sha256"] = ""
    payload["ecclesiastical_review"]["candidate_sha256"] = sha256_text(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True, choices=SERVICES)
    parser.add_argument("--language", required=True, choices=LANGS)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--document-title", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        payload = build_candidate(
            service=args.service,
            language=args.language,
            source=args.source.resolve(),
            source_id=args.source_id,
            source_url=args.source_url,
            document_title=args.document_title,
        )
    except Exception as exc:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(str(exc))
    output = args.output or ROOT / "data/services/candidates" / args.service / f"{args.language}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload["extraction_health"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"NATIVE_LITURGY_CANDIDATE_OK service={args.service} language={args.language} segments={len(payload['service']['segments'])} displayable=false")


if __name__ == "__main__":
    main()
