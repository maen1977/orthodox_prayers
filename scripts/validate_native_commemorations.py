"""Validate source-backed fixed commemorations without relaxing the native-lane contract."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "canonical" / "jerusalem_jordan_fixed_commemorations_native.json"
LANGS = ("ar", "en", "el")
LOCAL_JURISDICTIONS = {"jerusalem_patriarchate", "jerusalem_jordan"}
MONTH_LENGTHS = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def expected_slots() -> set[str]:
    return {f"{month:02d}-{day:02d}" for month, last in MONTH_LENGTHS.items() for day in range(1, last + 1)}


def valid_url(value: object) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def text_matches_lane(language: str, text: str) -> bool:
    if not text.strip():
        return False
    if language == "ar":
        return bool(ARABIC_RE.search(text))
    if language == "el":
        return bool(GREEK_RE.search(text))
    return bool(LATIN_RE.search(text))


def is_verified_local(language: str, entry: dict) -> bool:
    expected = {
        "ar": "VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE",
        "en": "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE",
        "el": "VERIFIED_NATIVE_LOCAL_GREEK_SOURCE",
    }[language]
    return (
        entry.get("evidence_status") == expected
        and entry.get("jurisdiction") in LOCAL_JURISDICTIONS
        and entry.get("comparative") is False
        and entry.get("fixed_slot_eligible") is True
    )


def validate(payload: dict) -> dict:
    errors: list[str] = []
    notices: list[str] = []
    expected = expected_slots()
    records = payload.get("records")
    if not isinstance(records, list):
        errors.append("records must be a list")
        records = []
    actual = [row.get("old_calendar_month_day") for row in records if isinstance(row, dict)]
    if len(records) != len(expected):
        errors.append(f"records count is {len(records)}; expected {len(expected)}")
    if len(set(actual)) != len(actual):
        errors.append("duplicate old-calendar slots are present")
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if missing:
        errors.append("missing slots: " + ", ".join(missing))
    if extra:
        errors.append("invalid slots: " + ", ".join(extra))

    artifacts = payload.get("source_artifacts")
    if not isinstance(artifacts, list):
        errors.append("source_artifacts must be a list")
        artifacts = []
    artifact_by_id = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("source_artifacts contains a non-object")
            continue
        source_id = str(artifact.get("source_id") or "")
        if not source_id or source_id in artifact_by_id:
            errors.append(f"invalid or duplicate source artifact id: {source_id}")
        artifact_by_id[source_id] = artifact
        if not valid_url(artifact.get("source_url")):
            errors.append(f"source artifact {source_id} has invalid source_url")
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("artifact_sha256") or "")):
            errors.append(f"source artifact {source_id} has invalid artifact_sha256")
        if artifact.get("language") not in LANGS:
            errors.append(f"source artifact {source_id} has invalid language")

    strict_slots = 0
    lane_counts = {lang: 0 for lang in LANGS}
    pending_counts = {lang: 0 for lang in LANGS}
    comparative_count = 0
    for row in records:
        if not isinstance(row, dict):
            errors.append("records contains a non-object")
            continue
        slot = str(row.get("old_calendar_month_day") or "")
        lanes = row.get("lanes")
        if not isinstance(lanes, dict):
            errors.append(f"{slot}: lanes must be an object")
            continue
        for key in lanes:
            if key not in LANGS:
                errors.append(f"{slot}: unknown language lane {key}")
        texts = {}
        verified = {}
        for language, entry in lanes.items():
            if language not in LANGS:
                continue
            if not isinstance(entry, dict):
                errors.append(f"{slot}/{language}: lane must be an object")
                continue
            text = str(entry.get("text") or "").strip()
            texts[language] = text
            lane_counts[language] += 1
            source_id = str(entry.get("source_id") or "")
            artifact = artifact_by_id.get(source_id)
            if artifact is None:
                errors.append(f"{slot}/{language}: source_id {source_id} is not declared")
            elif artifact.get("language") != language:
                errors.append(f"{slot}/{language}: source language does not match lane")
            if artifact is not None and artifact.get("jurisdiction") != entry.get("jurisdiction"):
                errors.append(f"{slot}/{language}: source jurisdiction does not match lane source jurisdiction")
            if not valid_url(entry.get("source_url")):
                errors.append(f"{slot}/{language}: invalid source_url")
            if entry.get("source_page") is None and not valid_url(entry.get("source_endpoint")):
                errors.append(f"{slot}/{language}: source_page or source_endpoint is required")
            if entry.get("source_page") is not None:
                try:
                    if int(entry.get("source_page")) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"{slot}/{language}: source_page must be a positive integer")
            if not text_matches_lane(language, text):
                status = str(entry.get("evidence_status") or "")
                if "REQUIRES_VISUAL_REVIEW" in status:
                    notices.append(f"{slot}/{language}: script anomaly retained as visual-review notice")
                else:
                    errors.append(f"{slot}/{language}: text does not match required native script")
            status = str(entry.get("evidence_status") or "")
            if not isinstance(entry.get("fixed_slot_eligible"), bool):
                errors.append(f"{slot}/{language}: fixed_slot_eligible must be boolean")
            comparative = entry.get("comparative") is True
            if comparative:
                comparative_count += 1
                if language != "en" or not status.startswith("COMPARATIVE_"):
                    errors.append(f"{slot}/{language}: comparative evidence must be English and explicitly comparative")
                if entry.get("jurisdiction") in LOCAL_JURISDICTIONS:
                    errors.append(f"{slot}/{language}: comparative evidence cannot claim local jurisdiction")
            if status.startswith("VERIFIED_NATIVE_LOCAL_"):
                if comparative or entry.get("jurisdiction") not in LOCAL_JURISDICTIONS:
                    errors.append(f"{slot}/{language}: verified-local status requires local non-comparative jurisdiction")
            verified[language] = is_verified_local(language, entry)
            if "REQUIRES_VISUAL_REVIEW" in status or status in {"pending_visual_review", "PER_RECORD_INTEGRITY_REVIEW"}:
                pending_counts[language] += 1
        if len(set(texts.values())) < len(texts) and len(texts) > 1:
            errors.append(f"{slot}: identical text appears in multiple language lanes; cross-language copying is forbidden")
        if all(verified.get(language, False) for language in LANGS):
            strict_slots += 1

    if payload.get("machine_translation_used") is not False:
        errors.append("machine_translation_used must be false")
    if payload.get("cross_language_fallback") is not False:
        errors.append("cross_language_fallback must be false")
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    if coverage.get("strict_named_local_gate") is not False:
        errors.append("coverage.strict_named_local_gate must remain false until all three local lanes are verified")
    if strict_slots != 0:
        notices.append(f"strict local three-language slots currently verified: {strict_slots}")
    if comparative_count and strict_slots:
        errors.append("comparative English evidence must never contribute to strict local gate")
    return {
        "ok": not errors,
        "errors": errors,
        "notices": notices,
        "coverage": {
            "records": len(records),
            "expected_slots": len(expected),
            "lane_counts": lane_counts,
            "pending_visual_review_counts": pending_counts,
            "comparative_lane_entries": comparative_count,
            "strict_local_three_language_slots": strict_slots,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    try:
        payload = json.loads(args.path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"ok": False, "errors": [f"cannot read {args.path}: {exc}"], "notices": []}, ensure_ascii=False))
        return 1
    report = validate(payload)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
