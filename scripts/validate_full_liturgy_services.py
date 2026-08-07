#!/usr/bin/env python3
"""Validate appointed-rite selection and beginning-to-end service availability.

This gate is intentionally fail-closed. A rite may be selected by the Typikon
engine while remaining unavailable in the reader; it may never be labelled
complete or replaced by another rite unless every published language lane has
its complete native service.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rolling_window_contract import metadata_errors

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
ADJACENT_OFFICES = (
    "proskomide",
    "pre_communion_prayers",
    "thanksgiving_after_communion",
)
STRICT_SCOPE = "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL"
DISPLAYABLE_STATUS = "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def service_index(payload: dict) -> dict[str, dict]:
    return {
        str(item.get("id") or ""): item
        for item in payload.get("services") or []
        if isinstance(item, dict) and str(item.get("id") or "")
    }


def native_text_stats(service: dict, language: str) -> tuple[int, int]:
    segments = service.get("segments") or []
    text_count = 0
    char_count = 0
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        localized = segment.get("title") if segment.get("type") == "section" else segment.get("text")
        if not isinstance(localized, dict):
            continue
        text = str(localized.get(language) or "").strip()
        if text:
            text_count += 1
            char_count += len(text)
    return text_count, char_count


def validate_static_contract(errors: list[str]) -> None:
    contract = load(ROOT / "canonical/full_liturgy_service_contract.json")
    editions = load(ROOT / "canonical/liturgy_service_editions.json")
    rules = load(ROOT / "canonical/liturgy_service_rules.json")

    rolling = contract.get("rolling_window") or {}
    if rolling.get("policy") != "ROLLING_FUTURE_WINDOW" or rolling.get("schema_version") != 2:
        errors.append("full contract rolling policy mismatch")
    if rolling.get("minimum_day_count") != 9 or rolling.get("maximum_day_count") != 9:
        errors.append("full contract must define the supported fixed nine-day horizon")
    if rolling.get("default_day_count") != 9:
        errors.append("full contract default rolling horizon must be 9 days")
    if contract.get("definition_of_complete", {}).get("partial_text_allowed") is not False:
        errors.append("partial liturgy text must be forbidden")
    if contract.get("definition_of_complete", {}).get("wrong_rite_fallback_allowed") is not False:
        errors.append("wrong-rite fallback must be forbidden")
    definition = contract.get("definition_of_complete", {})
    if definition.get("scope") != STRICT_SCOPE:
        errors.append("Divine Liturgy scope must be strict opening-blessing-to-dismissal")
    if definition.get("no_unappointed_material_allowed") is not True:
        errors.append("unappointed material must be forbidden inside the Divine Liturgy")
    excluded = set(definition.get("excludes_as_separate_offices") or [])
    for required in ("orthros_and_matins_gospel", "hours", "proskomide", "personal_pre_communion_prayers", "thanksgiving_after_communion"):
        if required not in excluded:
            errors.append(f"strict Liturgy contract does not separate {required}")
    rule_window = rules.get("rolling_window", {})
    if rule_window.get("policy") != "ROLLING_FUTURE_WINDOW" or rule_window.get("default_day_count") != 9:
        errors.append("liturgy rules rolling-window contract mismatch")

    libraries: dict[str, dict[str, dict]] = {}
    for language in LANGUAGES:
        path = ROOT / f"app/src/main/assets/data/native/library_{language}.json"
        libraries[language] = service_index(load(path))
        # Adjacent offices remain available as their own reader entries, but they
        # are not part of the Divine Liturgy completeness definition.
        for office in ADJACENT_OFFICES:
            if libraries[language].get(office) is None:
                errors.append(f"{language}: separate adjacent office missing: {office}")

    for rite, edition in (editions.get("editions") or {}).items():
        if not isinstance(edition, dict):
            continue
        displayable = bool(edition.get("displayable"))
        service_id = str(edition.get("service_id") or "")
        if displayable and not service_id:
            errors.append(f"{rite}: displayable rite has no service id")
            continue
        if displayable:
            for language in LANGUAGES:
                status = str(edition.get(language) or "")
                # Editorial/ecclesiastical review status is reported separately from
                # technical text completeness. A displayable service may retain an
                # explicit REVIEW_PENDING marker, but it may never be missing, blocked,
                # partial, or supplied through a different-language fallback.
                if any(marker in status for marker in ("MISSING", "BLOCK", "PARTIAL", "UNAVAILABLE")):
                    errors.append(f"{rite}.{language}: displayable rite lacks a complete native text: {status}")
                service = libraries[language].get(service_id)
                if service is None:
                    errors.append(f"{rite}.{language}: service missing from native library: {service_id}")
                    continue
                text_count, chars = native_text_stats(service, language)
                if text_count < 40 or chars < 10_000:
                    errors.append(
                        f"{rite}.{language}: service too short for complete claim texts={text_count} chars={chars}"
                    )

    # The recovered Arabic Presanctified file is explanatory material, not the
    # full service. Keep this invariant explicit until a reviewed Unicode source
    # replaces it.
    presanctified = (editions.get("editions") or {}).get("presanctified") or {}
    if presanctified.get("displayable"):
        ar_service = libraries["ar"].get(str(presanctified.get("service_id") or ""))
        text_count, chars = native_text_stats(ar_service or {}, "ar")
        if text_count < 100 or chars < 20_000:
            errors.append("Arabic Presanctified service may not be marked displayable while still partial")


def validate_day(day: dict, expected_date: str, errors: list[str]) -> None:
    if day.get("date_iso") != expected_date:
        errors.append(f"{expected_date}: date mismatch")
        return
    selection = day.get("liturgy_service_selection")
    if not isinstance(selection, dict):
        errors.append(f"{expected_date}: appointed liturgy selection missing")
        return
    selected_type = str(selection.get("service_type") or "")
    service_form = str(selection.get("service_form") or "")
    if not selected_type:
        errors.append(f"{expected_date}: appointed liturgy type missing")
    if not service_form:
        errors.append(f"{expected_date}: service form missing")
    if not isinstance(selection.get("reason"), dict):
        errors.append(f"{expected_date}: selection reason missing")
    if selection.get("wrong_liturgy_fallback_allowed") is not False:
        errors.append(f"{expected_date}: wrong-rite fallback is not disabled")

    service = service_index(day).get("divine_liturgy")
    if service is None:
        errors.append(f"{expected_date}: divine_liturgy service missing")
        return
    if service.get("selected_liturgy_type") != selected_type:
        errors.append(f"{expected_date}: service type does not match selection")
    publication_status = str(service.get("publication_status") or "")
    if selected_type == "no_divine_liturgy":
        if publication_status != "NO_DIVINE_LITURGY_APPOINTED":
            errors.append(f"{expected_date}: no-liturgy day has invalid status")
        return
    if selected_type == "typikon_override_required":
        errors.append(f"{expected_date}: dated Typikon ruling still required")
        return
    if selection.get("displayable") is not True:
        errors.append(f"{expected_date}: selected rite lacks a complete native edition")
    if service.get("full_service_complete") is not True:
        errors.append(f"{expected_date}: service is not complete from beginning to end")
    if publication_status != DISPLAYABLE_STATUS:
        errors.append(f"{expected_date}: invalid full-service publication status {publication_status}")
    if not str(service.get("extends_service_id") or ""):
        errors.append(f"{expected_date}: full service template missing")


def validate_payload(path: Path, errors: list[str]) -> None:
    payload = load(path)
    rolling = payload.get("rolling_week")
    if not isinstance(rolling, dict):
        validate_day(payload, str(payload.get("date_iso") or ""), errors)
        return
    future = [item for item in payload.get("weekly_days") or [] if isinstance(item, dict)]
    try:
        start = __import__("datetime").date.fromisoformat(str(rolling.get("start_date") or ""))
    except ValueError:
        errors.append(f"{path}: invalid rolling start date")
        return
    errors.extend(f"{path}: {error}" for error in metadata_errors(rolling, start, len(future)))
    day_count = int(rolling.get("day_count") or 0)
    days = [payload, *future]
    if len(days) != day_count:
        errors.append(f"{path}: expected {day_count} days, found {len(days)}")
        return
    for offset, day in enumerate(days):
        validate_day(day, (start + __import__("datetime").timedelta(days=offset)).isoformat(), errors)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="Optional daily or moving-window package to validate")
    args = parser.parse_args()
    errors: list[str] = []
    validate_static_contract(errors)
    if args.path:
        validate_payload(ROOT / args.path, errors)
    if errors:
        for error in errors[:100]:
            print(f"FULL_LITURGY_ERROR {error}")
        raise SystemExit(f"FULL_LITURGY_INVALID errors={len(errors)}")
    print("FULL_LITURGY_OK rolling_window=9 default_days=9 wrong_rite_fallback=false scope=beginning_to_end")


if __name__ == "__main__":
    main()
