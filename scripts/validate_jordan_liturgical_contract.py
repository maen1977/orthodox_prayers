#!/usr/bin/env python3
"""Fail-closed Jordan liturgical reference and Divine Liturgy overlay gate."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from orthodox_integrity import parse_reference  # noqa: E402

CONTRACT = ROOT / "canonical" / "jordan_liturgical_contract.json"
MARKERS = {
    "epistle": "[فصل من رسالة اليوم]",
    "gospel": "[فصل الإنجيل المعيّن لهذا اليوم]",
}
APPROVED_REFERENCE_AUTHORITIES = {
    "orthodox_jordan",
    "jerusalem_patriarchate",
    "official_greek_orthodox",
    "orthodox_church_in_america",
}

INCOMPLETE_TOKENS = (
    "[طروبارية اليوم]", "[القنداق]", "[اسم الإنجيلي]",
    "[فصل من رسالة اليوم]", "[فصل الإنجيل المعيّن لهذا اليوم]",
    "[آية المناولة]", "إلى آخره", "الخ...", "مختصر القداس",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reading_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("readings") or []:
        if isinstance(item, dict) and item.get("kind") in {"epistle", "gospel"}:
            kind = str(item["kind"])
            if kind in out:
                raise ValueError(f"duplicate {kind} reading")
            out[kind] = item
    return out


def canonical(item: dict[str, Any]) -> str:
    value = str(item.get("integrity", {}).get("canonical_reference") or "").strip()
    if value:
        return value
    refs = item.get("reference") if isinstance(item.get("reference"), dict) else {}
    for lang in ("en", "ar", "el"):
        raw = str(refs.get(lang) or "").strip()
        if not raw:
            continue
        try:
            return parse_reference(raw)[0]
        except Exception:
            continue
    raise ValueError(f"cannot canonicalize {item.get('kind')} reference")


def service(payload: dict[str, Any], service_id: str) -> dict[str, Any]:
    for item in payload.get("services") or []:
        if isinstance(item, dict) and item.get("id") == service_id:
            return item
    raise ValueError(f"missing service {service_id}")


def validate_payload(payload: dict[str, Any], *, expected_date: str | None, require_record: bool, require_authority: bool = False, require_complete_liturgy: bool) -> list[str]:
    errors: list[str] = []
    date_iso = str(payload.get("date_iso") or "")
    if expected_date and date_iso != expected_date:
        errors.append(f"date mismatch: expected {expected_date}, got {date_iso or '<missing>'}")

    records = load(CONTRACT).get("records", {})
    record = records.get(date_iso)
    publication = payload.get("publication") if isinstance(payload.get("publication"), dict) else {}
    selected = str(publication.get("selected_source") or "")
    evidence = payload.get("source_evidence") if isinstance(payload.get("source_evidence"), list) else []

    # Historical checked-in snapshots that predate the jurisdiction contract are
    # still structurally valid for repository regression tests. The strict lock
    # is mandatory only for a pinned date or an explicit publication/release gate.
    if not isinstance(record, dict) and not (require_record or require_authority or require_complete_liturgy):
        return errors

    if publication.get("jurisdiction_lock") != "ORTHODOX_JORDAN_FAIL_CLOSED":
        errors.append("publication is missing ORTHODOX_JORDAN_FAIL_CLOSED lock")
    if publication.get("authority_mode") not in {None, "JORDAN_OLD_CALENDAR_OFFICIAL_REFERENCE_GATE"}:
        errors.append("publication authority_mode is unsupported")

    if require_authority:
        current_selected = any(
            isinstance(item, dict)
            and item.get("id") == selected
            and item.get("status") == "current"
            and item.get("date_iso") == date_iso
            and str(item.get("epistle_reference") or "").strip()
            and str(item.get("gospel_reference") or "").strip()
            for item in evidence
        )
        if selected not in APPROVED_REFERENCE_AUTHORITIES or not current_selected:
            errors.append("current Jordan-compatible official reference evidence is required for the selected source")
        if isinstance(record, dict) and selected != "orthodox_jordan":
            errors.append("a pinned Jordan date must publish through orthodox_jordan authority")

    if not isinstance(record, dict) and require_record:
        errors.append(f"no pinned Jordan liturgical record for {date_iso}")

    try:
        readings = reading_map(payload)
    except ValueError as exc:
        return errors + [str(exc)]
    if set(readings) != {"epistle", "gospel"}:
        errors.append("payload must contain exactly one epistle and one gospel")
        return errors

    actual: dict[str, str] = {}
    for kind in ("epistle", "gospel"):
        try:
            actual[kind] = canonical(readings[kind])
        except ValueError as exc:
            errors.append(str(exc))
            continue
        bodies = readings[kind].get("body") if isinstance(readings[kind].get("body"), dict) else {}
        if not any(str(bodies.get(lang) or "").strip() for lang in ("ar", "en", "el")):
            errors.append(f"{kind} has no verified native text in any language lane")

    if isinstance(record, dict):
        expected = {
            "epistle": str(record.get("epistle_canonical") or ""),
            "gospel": str(record.get("gospel_canonical") or ""),
        }
        for kind in ("epistle", "gospel"):
            if actual.get(kind) and actual[kind] != expected[kind]:
                errors.append(f"Jordan {kind} mismatch for {date_iso}: expected {expected[kind]}, got {actual[kind]}")
    else:
        expected = actual

    try:
        liturgy = service(payload, "divine_liturgy")
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    if liturgy.get("dynamic_date") != date_iso:
        errors.append("Divine Liturgy overlay date does not match payload date")
    daily_contract = liturgy.get("daily_reading_contract") if isinstance(liturgy.get("daily_reading_contract"), dict) else {}
    if daily_contract.get("authority") != "orthodox_jordan" or daily_contract.get("date_iso") != date_iso:
        errors.append("Divine Liturgy is missing its Jordan daily-reading contract")
    for kind in ("epistle", "gospel"):
        if actual.get(kind) and daily_contract.get(f"{kind}_canonical") != actual[kind]:
            errors.append(f"Divine Liturgy {kind} canonical metadata mismatch")
        replacements = liturgy.get("segment_replacements") if isinstance(liturgy.get("segment_replacements"), dict) else {}
        rendered = replacements.get(MARKERS[kind])
        if not isinstance(rendered, dict):
            errors.append(f"Divine Liturgy missing {kind} replacement")
            continue
        bodies = readings[kind].get("body") if isinstance(readings[kind].get("body"), dict) else {}
        for lang in ("ar", "en", "el"):
            body = str(bodies.get(lang) or "").strip()
            block = str(rendered.get(lang) or "")
            if body and body not in block:
                errors.append(f"Divine Liturgy {kind}.{lang} does not contain exact verified reading body")

    if require_complete_liturgy:
        base = load(ROOT / "app/src/main/assets/data/library.json")
        base_service = next((x for x in base.get("services", []) if x.get("id") == "divine_liturgy"), None)
        if not isinstance(base_service, dict):
            errors.append("static Divine Liturgy template is missing")
        else:
            rendered_base = json.dumps(base_service, ensure_ascii=False)
            replacements = liturgy.get("segment_replacements") if isinstance(liturgy.get("segment_replacements"), dict) else {}
            inline = liturgy.get("inline_replacements") if isinstance(liturgy.get("inline_replacements"), dict) else {}
            for marker, localized in {**replacements, **inline}.items():
                if isinstance(localized, dict):
                    replacement = next((str(localized.get(lang) or "") for lang in ("ar", "en", "el") if str(localized.get(lang) or "").strip()), "")
                else:
                    replacement = str(localized or "")
                rendered_base = rendered_base.replace(marker, replacement)
            for token in INCOMPLETE_TOKENS:
                if token in rendered_base:
                    errors.append(f"complete Divine Liturgy claim blocked by unresolved token: {token}")
            required_markers = record.get("required_daily_markers") if isinstance(record, dict) else MARKERS.values()
            for marker in required_markers or []:
                value = replacements.get(marker)
                if not isinstance(value, dict) or not any(str(value.get(lang) or "").strip() for lang in ("ar", "en", "el")):
                    errors.append(f"required daily Liturgy marker is empty: {marker}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--expected-date")
    parser.add_argument("--require-record", action="store_true")
    parser.add_argument("--require-jordan-authority", action="store_true")
    parser.add_argument("--require-complete-liturgy", action="store_true")
    args = parser.parse_args()
    path = ROOT / args.path
    payload = load(path)
    errors = validate_payload(
        payload,
        expected_date=args.expected_date,
        require_record=args.require_record,
        require_authority=args.require_jordan_authority,
        require_complete_liturgy=args.require_complete_liturgy,
    )
    if errors:
        for error in errors:
            print("JORDAN_CONTRACT_ERROR", error)
        raise SystemExit(1)
    print(f"JORDAN_CONTRACT_OK date={payload.get('date_iso')} record={'yes' if payload.get('date_iso') in load(CONTRACT).get('records', {}) else 'not-required'}")

if __name__ == "__main__":
    main()
