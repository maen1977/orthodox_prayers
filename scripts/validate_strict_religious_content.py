#!/usr/bin/env python3
"""Fail-closed automated audit for Scripture, commemorations, dates, and native lanes.

This gate is intentionally deterministic. It does not generate or translate religious
text. It verifies the exact text, canonical references, verse-level hashes, source
evidence, and truthful absence semantics before build, signing, or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from native_text_contract import LANGUAGES, script_errors, sha256_text  # noqa: E402
from orthodox_integrity import canonical_reference_is_valid  # noqa: E402

ALLOWED_EXACT_STATUSES = {
    "VERIFIED_EXACT_NATIVE_SOURCE",
    "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
    "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
}
SCRIPTURE_KINDS = {"epistle", "gospel", "matins_gospel"}
BAD_STATUS_PREFIXES = ("UNAVAILABLE", "PENDING", "NO_VERIFIED", "MISSING", "REJECTED", "BLOCKED")
GENERIC_COMMEMORATION_PATTERNS = (
    re.compile(r"تذكار اليوم بحسب التقويم الكنسي القديم", re.I),
    re.compile(r"تذكار اليوم ي?ُ?ستكمل من التحديث الموثق", re.I),
    re.compile(r"(?:Today[’']s|Daily) commemoration according to the old (?:church|ecclesiastical) calendar", re.I),
    re.compile(r"Daily commemoration is completed by the verified update", re.I),
    re.compile(r"(?:Ἡ σημερινὴ μνήμη|Μνήμη τῆς ἡμέρας) κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο", re.I),
    re.compile(r"Ἡ μνήμη τῆς ἡμέρας συμπληρώνεται", re.I),
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def text(value: object) -> str:
    return str(value or "").strip()


def localized(value: object, language: str) -> str:
    return text(value.get(language)) if isinstance(value, dict) else ""


def is_bad_status(value: object) -> bool:
    status = text(value).upper()
    return any(status.startswith(prefix) for prefix in BAD_STATUS_PREFIXES)


def is_generic_commemoration(value: str) -> bool:
    candidate = text(value)
    return not candidate or any(pattern.search(candidate) for pattern in GENERIC_COMMEMORATION_PATTERNS)


def all_days(payload: dict[str, Any]) -> list[dict[str, Any]]:
    days = [payload]
    days.extend(item for item in payload.get("weekly_days") or [] if isinstance(item, dict))
    return days


def canonical_reference(reading: dict[str, Any]) -> str:
    return text((reading.get("integrity") or {}).get("canonical_reference"))


def validate_reference_and_hashes(
    reading: dict[str, Any],
    kind: str,
    pointer: str,
    languages: tuple[str, ...],
    require_complete: bool,
    errors: list[str],
) -> None:
    canonical = canonical_reference(reading)
    if not canonical or not canonical_reference_is_valid(canonical):
        errors.append(f"{pointer}: invalid canonical_reference {canonical or '<missing>'}")

    if reading.get("translation_locked") is not True:
        errors.append(f"{pointer}: translation_locked must be true")
    integrity = reading.get("integrity") or {}
    if integrity.get("status") != "NATIVE_LANGUAGE_LANES_ENFORCED":
        errors.append(f"{pointer}: native-lane integrity status is invalid")
    if integrity.get("ai_translation_used") not in (None, False):
        errors.append(f"{pointer}: AI translation is forbidden")
    if integrity.get("automatic_diacritization_used") not in (None, False):
        errors.append(f"{pointer}: automatic diacritization is forbidden")

    bodies = reading.get("body") if isinstance(reading.get("body"), dict) else {}
    references = reading.get("reference") if isinstance(reading.get("reference"), dict) else {}
    evidence_map = reading.get("native_source_verification") if isinstance(reading.get("native_source_verification"), dict) else {}

    for language in languages:
        body = localized(bodies, language)
        reference = localized(references, language)
        evidence = evidence_map.get(language) if isinstance(evidence_map.get(language), dict) else {}
        if require_complete and not body:
            errors.append(f"{pointer}.{language}: exact Scripture body is missing")
        if require_complete and not reference:
            errors.append(f"{pointer}.{language}: display reference is missing")
        if not body:
            continue

        if evidence.get("status") not in ALLOWED_EXACT_STATUSES:
            errors.append(f"{pointer}.{language}: exact native-source status is missing")
        if evidence.get("text_available") is not True:
            errors.append(f"{pointer}.{language}: text_available must be true")
        if reference and evidence.get("reference_available") is not True:
            errors.append(f"{pointer}.{language}: reference_available must be true")
        if evidence.get("ai_translation_used") is not False:
            errors.append(f"{pointer}.{language}: ai_translation_used must be false")
        if evidence.get("automatic_diacritization_used") is not False:
            errors.append(f"{pointer}.{language}: automatic_diacritization_used must be false")
        if not text(evidence.get("source_id")):
            errors.append(f"{pointer}.{language}: source_id is missing")
        if not text(evidence.get("source_url")):
            errors.append(f"{pointer}.{language}: source_url is missing")
        evidence_canonical = text(evidence.get("canonical_reference"))
        if evidence_canonical and canonical and evidence_canonical != canonical:
            errors.append(
                f"{pointer}.{language}: evidence canonical reference {evidence_canonical} != {canonical}"
            )
        expected_hash = text(evidence.get("text_sha256"))
        actual_hash = sha256_text(body)
        if expected_hash != actual_hash:
            errors.append(f"{pointer}.{language}: text_sha256 mismatch")
        for problem in script_errors(language, body):
            errors.append(f"{pointer}.{language}: {problem}")

        verse_hashes = evidence.get("verse_hashes")
        verse_count = evidence.get("verse_count")
        if verse_hashes is not None or verse_count is not None:
            lines = body.splitlines()
            expected_verse_hashes = [sha256_text(line) for line in lines]
            if verse_count != len(lines):
                errors.append(
                    f"{pointer}.{language}: verse_count {verse_count} != rendered lines {len(lines)}"
                )
            if verse_hashes != expected_verse_hashes:
                errors.append(f"{pointer}.{language}: verse_hashes do not match exact rendered lines")


def validate_readings(
    day: dict[str, Any],
    pointer: str,
    languages: tuple[str, ...],
    require_complete: bool,
    errors: list[str],
) -> int:
    readings = [item for item in day.get("readings") or [] if isinstance(item, dict)]
    by_kind: dict[str, dict[str, Any]] = {}
    for index, reading in enumerate(readings):
        kind = text(reading.get("kind"))
        if kind in by_kind:
            errors.append(f"{pointer}: duplicate reading kind {kind}")
        else:
            by_kind[kind] = reading
        if kind in SCRIPTURE_KINDS:
            validate_reference_and_hashes(
                reading,
                kind,
                f"{pointer}.readings[{index}]({kind})",
                languages,
                require_complete,
                errors,
            )
    if require_complete:
        for required in ("epistle", "gospel"):
            if required not in by_kind:
                errors.append(f"{pointer}: required {required} is missing")
    return sum(1 for key in by_kind if key in SCRIPTURE_KINDS)


def object_title(value: object, language: str) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("title", "name", "commemorations"):
        child = value.get(key)
        found = localized(child, language)
        if found:
            return found
    return ""


def validate_commemoration(
    day: dict[str, Any],
    pointer: str,
    languages: tuple[str, ...],
    errors: list[str],
) -> str:
    for key, status_key in (
        ("local_commemoration", "local_commemoration_status"),
        ("commemoration", "commemoration_status"),
    ):
        value = day.get(key)
        if not isinstance(value, dict):
            continue
        status = text(day.get(status_key) or value.get("status"))
        if is_bad_status(status):
            continue
        missing = [language for language in languages if not object_title(value, language)]
        if missing:
            errors.append(f"{pointer}.{key}: verified title missing for {','.join(missing)}")
            return "absent"
        return "verified"

    occasion_status = text(day.get("occasion_status"))
    feast = day.get("feast") if isinstance(day.get("feast"), dict) else {}
    note = day.get("note") if isinstance(day.get("note"), dict) else {}
    visible = {language: localized(feast, language) or localized(note, language) for language in languages}
    non_generic = {language: value for language, value in visible.items() if not is_generic_commemoration(value)}
    if is_bad_status(occasion_status):
        if non_generic:
            errors.append(f"{pointer}: pending/unavailable occasion contains displayable commemoration text")
        return "absent"
    if non_generic:
        missing = [language for language in languages if is_generic_commemoration(visible.get(language, ""))]
        if missing:
            errors.append(f"{pointer}: commemoration is not complete in native lanes {','.join(missing)}")
        return "verified"
    return "absent"


def validate_dates(days: list[dict[str, Any]], expected_date: str | None, errors: list[str]) -> None:
    if expected_date and text(days[0].get("date_iso")) != expected_date:
        errors.append(
            f"root date mismatch expected={expected_date} actual={text(days[0].get('date_iso')) or '<missing>'}"
        )
    parsed: list[date] = []
    for index, day_payload in enumerate(days):
        raw = text(day_payload.get("date_iso"))
        try:
            parsed.append(date.fromisoformat(raw))
        except ValueError:
            errors.append(f"days[{index}]: invalid date_iso {raw or '<missing>'}")
            return
    for index in range(1, len(parsed)):
        expected = parsed[index - 1] + timedelta(days=1)
        if parsed[index] != expected:
            errors.append(
                f"days[{index}]: non-consecutive date expected={expected.isoformat()} actual={parsed[index].isoformat()}"
            )


def write_report(path: Path, source: Path, days: int, readings: int, present: int, absent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Strict religious-content audit\n\n"
        f"- Source: `{source.as_posix()}`\n"
        f"- Days checked: **{days}**\n"
        f"- Scripture readings checked: **{readings}**\n"
        f"- Displayable commemorations: **{present}**\n"
        f"- Truthfully absent commemorations: **{absent}**\n"
        "- Calendar files: verified separately by the immutable 2026–2050 calendar lock.\n"
        "- Result: **PASS**\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--expected-date")
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    payload = load(path)
    days = all_days(payload)
    languages = (args.language,) if args.language else LANGUAGES
    errors: list[str] = []
    validate_dates(days, args.expected_date, errors)

    reading_count = 0
    present = 0
    absent = 0
    for index, day_payload in enumerate(days):
        pointer = f"days[{index}]({text(day_payload.get('date_iso')) or 'unknown'})"
        reading_count += validate_readings(day_payload, pointer, languages, args.require_complete, errors)
        state = validate_commemoration(day_payload, pointer, languages, errors)
        present += state == "verified"
        absent += state == "absent"

    if errors:
        for error in dict.fromkeys(errors):
            print(f"STRICT_RELIGIOUS_CONTENT_ERROR {error}")
        raise SystemExit(1)

    if args.report:
        report = Path(args.report)
        if not report.is_absolute():
            report = ROOT / report
        write_report(report, path.relative_to(ROOT), len(days), reading_count, present, absent)
    print(
        "STRICT_RELIGIOUS_CONTENT_OK "
        f"path={path.relative_to(ROOT)} days={len(days)} readings={reading_count} "
        f"commemorations_present={present} commemorations_absent={absent} "
        f"languages={','.join(languages)}"
    )


if __name__ == "__main__":
    main()
