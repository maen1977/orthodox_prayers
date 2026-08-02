#!/usr/bin/env python3
"""Build an automated, cross-calendar source comparison for the signed nine-day window.

This module never asks an AI model to choose a reading, translate a text, or invent a
commemoration. It compares already-generated references with official source observations,
the internal Jerusalem/Jordan calendar, and preserved local-authority records. Calendar
profiles are kept separate so a new-calendar disagreement cannot silently override the
Jerusalem/Jordan old-calendar package.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rolling_window_contract import resolve_day_count  # noqa: E402
from source_connectors import (  # noqa: E402
    ConnectorDefinition,
    ConnectorObservation,
    load_registry,
    normalize_reference,
    observe_connector,
    probe_service_links,
)

POLICY_PATH = ROOT / "canonical" / "source_comparison_policy.json"
CALENDAR_PATH = ROOT / "canonical" / "internal_calendar_2026_2050.json"
LOCAL_PATH = ROOT / "canonical" / "local_commemorations.json"
HEALTH_PATH = ROOT / "data" / "sources" / "health" / "current.json"
OUTPUT_DIR = ROOT / "data" / "sources" / "comparison"
ASSET_PATH = ROOT / "app" / "src" / "main" / "assets" / "data" / "source_comparison.json"
CURRENT_DAILY = ROOT / "data" / "calendar" / "today.json"

GENERIC_FEAST_MARKERS = (
    "تذكار اليوم بحسب التقويم الكنسي القديم",
    "تذكار اليوم يُستكمل من التحديث الموثق",
    "today’s commemoration according to the old church calendar",
    "daily commemoration is completed by the verified update",
    "ἡ σημερινὴ μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο",
    "ἡ μνήμη τῆς ἡμέρας συμπληρώνεται ἀπὸ τὴν ἐπαληθευμένη ἐνημέρωση",
)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(default)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def package_days(payload: dict[str, Any], start: date, day_count: int) -> list[dict[str, Any]]:
    days = [payload]
    days.extend(item for item in payload.get("weekly_days") or [] if isinstance(item, dict))
    if len(days) != day_count:
        raise SystemExit(f"source comparison expected {day_count} package days, found {len(days)}")
    for offset, item in enumerate(days):
        expected = (start + timedelta(days=offset)).isoformat()
        if item.get("date_iso") != expected:
            raise SystemExit(
                f"source comparison date mismatch at offset {offset}: "
                f"{item.get('date_iso')} != {expected}"
            )
    return days


def published_reference(day_payload: dict[str, Any], kind: str) -> str:
    for reading in day_payload.get("readings") or []:
        if not isinstance(reading, dict) or reading.get("kind") != kind:
            continue
        reference = reading.get("reference") or {}
        if isinstance(reference, dict):
            for language in ("en", "ar", "el"):
                value = str(reference.get(language) or "").strip()
                if value:
                    return value
        value = str(reference or "").strip()
        if value:
            return value
    return ""


def reading_evidence(day_payload: dict[str, Any], kind: str) -> dict[str, Any]:
    for reading in day_payload.get("readings") or []:
        if isinstance(reading, dict) and reading.get("kind") == kind:
            verification = reading.get("native_source_verification") or {}
            languages = {}
            for language in ("ar", "en", "el"):
                item = verification.get(language) if isinstance(verification, dict) else None
                if isinstance(item, dict):
                    languages[language] = {
                        "status": item.get("status"),
                        "source_id": item.get("source_id"),
                        "canonical_reference": item.get("canonical_reference"),
                        "text_sha256": item.get("text_sha256"),
                        "ai_translation_used": item.get("ai_translation_used"),
                    }
            return {"languages": languages}
    return {"languages": {}}


def feast_texts(day_payload: dict[str, Any]) -> dict[str, str]:
    feast = day_payload.get("feast") or {}
    if not isinstance(feast, dict):
        return {"ar": str(feast or ""), "en": "", "el": ""}
    return {language: str(feast.get(language) or "").strip() for language in ("ar", "en", "el")}


def generic_feast(feast: dict[str, str]) -> bool:
    folded = " ".join(feast.values()).casefold()
    return any(marker.casefold() in folded for marker in GENERIC_FEAST_MARKERS)


def internal_records() -> dict[str, dict[str, Any]]:
    payload = load_json(CALENDAR_PATH, {"days": []})
    return {
        str(item.get("date_iso") or item.get("date") or ""): item
        for item in payload.get("days") or []
        if isinstance(item, dict) and (item.get("date_iso") or item.get("date"))
    }


def local_records() -> dict[str, dict[str, Any]]:
    payload = load_json(LOCAL_PATH, {"records": {}})
    records = payload.get("records") or {}
    return records if isinstance(records, dict) else {}


def anchor_observations() -> list[dict[str, Any]]:
    payload = load_json(HEALTH_PATH, {"observations": []})
    return [item for item in payload.get("observations") or [] if isinstance(item, dict)]


def fixture_bytes(fixture_dir: Path | None, connector_id: str, target: date) -> bytes | None:
    if fixture_dir is None:
        return None
    candidates = (
        fixture_dir / f"{connector_id}-{target.isoformat()}.html",
        fixture_dir / f"{connector_id}-{target.isoformat()}.json",
        fixture_dir / f"{connector_id}.html",
        fixture_dir / f"{connector_id}.json",
        fixture_dir / f"{connector_id}.txt",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_bytes()
    return None


def offline_observation(definition: ConnectorDefinition, target: date) -> ConnectorObservation:
    item = ConnectorObservation(
        connector_id=definition.id,
        source_id=definition.source_id,
        official=definition.official,
        authority_tier=definition.authority_tier,
        publication_role=definition.publication_role,
        calendar_profile=definition.calendar_profile,
        target_date=target.isoformat(),
        url=definition.url_for(target),
        status="offline_not_checked",
        checked_at_utc=utc_now(),
        confidence=0.0,
        rights_mode=definition.rights_mode,
        reason="network disabled and no fixture supplied",
    )
    return item


def observe_with_retries(
    definition: ConnectorDefinition,
    target: date,
    *,
    offline: bool,
    fixture_dir: Path | None,
    attempts: int,
    initial_backoff: int,
    maximum_backoff: int,
    fetch_cache: dict[str, tuple[int, bytes, str]] | None = None,
) -> ConnectorObservation:
    raw = fixture_bytes(fixture_dir, definition.id, target)
    if offline and raw is None:
        return offline_observation(definition, target)
    last: ConnectorObservation | None = None
    for attempt in range(1, max(1, attempts) + 1):
        last = observe_connector(definition, target, raw=raw, fetch_cache=fetch_cache)
        if definition.parser == "dcs_service_probe" and raw is None and not offline:
            last = probe_service_links(last, definition)
        if last.status not in {"network_error", "http_error", "parser_error"}:
            break
        if raw is not None or attempt >= attempts:
            break
        delay = min(maximum_backoff, initial_backoff * (2 ** (attempt - 1)))
        time.sleep(max(0, delay))
    assert last is not None
    last.warnings.append(f"attempts={attempt}")
    return last


def normalize_observation_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "connector_id": item.get("connector_id"),
        "source_id": item.get("source_id"),
        "official": bool(item.get("official")),
        "authority_tier": item.get("authority_tier"),
        "calendar_profile": item.get("calendar_profile"),
        "target_date": item.get("target_date"),
        "detected_date": item.get("detected_date"),
        "status": item.get("status"),
        "confidence": float(item.get("confidence") or 0.0),
        "url": item.get("url"),
        "http_status": item.get("http_status"),
        "content_sha256": item.get("content_sha256"),
        "structure_sha256": item.get("structure_sha256"),
        "content_bytes": item.get("content_bytes"),
        "epistle_reference": item.get("epistle_reference"),
        "gospel_reference": item.get("gospel_reference"),
        "commemorations": item.get("commemorations") or [],
        "service_links": item.get("service_links") or [],
        "reason": item.get("reason"),
        "warnings": item.get("warnings") or [],
        "rights_mode": item.get("rights_mode"),
    }


def internal_reference(record: dict[str, Any], kind: str) -> str:
    readings = record.get("reading_references") or {}
    item = readings.get(kind) if isinstance(readings, dict) else None
    if not isinstance(item, dict):
        return ""
    return str(item.get("display_reference") or (item.get("reference") or {}).get("en") or "").strip()


def source_evidence_observations(day_payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for item in day_payload.get("source_evidence") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id") or "")
        calendar_profile = "jerusalem_old_calendar" if source_id in {"orthodox_jordan", "jerusalem_patriarchate"} else "unknown"
        results.append(
            {
                "connector_id": f"payload:{source_id}",
                "source_id": source_id,
                "official": bool(item.get("official", True)),
                "authority_tier": item.get("priority"),
                "calendar_profile": calendar_profile,
                "target_date": item.get("date_iso"),
                "detected_date": item.get("date_iso"),
                "status": item.get("status"),
                "confidence": 0.9 if item.get("status") == "current" else 0.55,
                "url": item.get("url"),
                "http_status": None,
                "content_sha256": item.get("sha256"),
                "content_bytes": None,
                "epistle_reference": item.get("epistle_reference"),
                "gospel_reference": item.get("gospel_reference"),
                "commemorations": [],
                "service_links": [],
                "reason": item.get("reason"),
                "warnings": [],
                "rights_mode": "payload_source_evidence",
            }
        )
    return results


def compare_reference(
    field_name: str,
    published: str,
    internal: str,
    internal_status: str,
    observations: list[dict[str, Any]],
    calendar_groups: dict[str, str],
    local_connector: str,
) -> dict[str, Any]:
    normalized_published = normalize_reference(published)
    result: dict[str, Any] = {
        "published": published,
        "normalized_published": normalized_published,
        "internal": internal or None,
        "internal_status": internal_status,
        "status": "UNCONFIRMED",
        "agreements": [],
        "conflicts": [],
        "warnings": [],
        "errors": [],
    }
    if not normalized_published:
        result["errors"].append(f"{field_name} is missing")
        result["status"] = "BLOCK"
        return result

    normalized_internal = normalize_reference(internal)
    if internal_status.startswith("PINNED_") and normalized_internal:
        if normalized_internal != normalized_published:
            result["errors"].append(
                f"pinned internal {field_name} conflict: {normalized_internal} != {normalized_published}"
            )
        else:
            result["agreements"].append({"source": "internal_calendar", "calendar_group": "jerusalem_jordan"})

    for item in observations:
        observed_value = str(item.get(field_name) or "").strip()
        normalized_observed = normalize_reference(observed_value)
        if not normalized_observed:
            continue
        exact_date = (item.get("status") == "current") or (bool(item.get("detected_date")) and str(item.get("detected_date")) == str(item.get("target_date") or ""))
        if not exact_date and str(item.get("status")) not in {"current"}:
            continue
        connector_id = str(item.get("connector_id") or "")
        profile = str(item.get("calendar_profile") or "unknown")
        group = calendar_groups.get(profile, profile)
        entry = {
            "connector_id": connector_id,
            "source_id": item.get("source_id"),
            "calendar_profile": profile,
            "calendar_group": group,
            "reference": observed_value,
            "normalized": normalized_observed,
            "confidence": float(item.get("confidence") or 0.0),
            "url": item.get("url"),
        }
        if normalized_observed == normalized_published:
            result["agreements"].append(entry)
            continue
        result["conflicts"].append(entry)
        if connector_id == local_connector or connector_id == "payload:orthodox_jordan":
            result["errors"].append(
                f"local authority {field_name} conflict: {normalized_observed} != {normalized_published}"
            )
        elif group == "jerusalem_jordan":
            result["errors"].append(
                f"same-calendar {field_name} conflict from {connector_id}: "
                f"{normalized_observed} != {normalized_published}"
            )
        else:
            result["warnings"].append(
                f"cross-calendar {field_name} differs at {connector_id}; it cannot override Jerusalem/Jordan"
            )

    if result["errors"]:
        result["status"] = "BLOCK"
    else:
        authority_agreements = [
            item for item in result["agreements"]
            if item.get("calendar_group") == "jerusalem_jordan"
            or item.get("connector_id") in {local_connector, "payload:orthodox_jordan", "internal_calendar"}
        ]
        independent = {
            str(item.get("source_id") or item.get("source") or item.get("connector_id"))
            for item in result["agreements"]
        }
        if len(independent) >= 2:
            result["status"] = "CONFIRMED_MULTI_SOURCE"
        elif authority_agreements:
            result["status"] = "CONFIRMED_AUTHORITY"
        elif result["agreements"]:
            result["status"] = "CONFIRMED_CROSS_CHECK"
        else:
            result["status"] = "INTERNAL_FAILSAFE"
    return result


def day_decision(
    day_payload: dict[str, Any],
    target: date,
    observations: list[dict[str, Any]],
    internal: dict[str, Any],
    local: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    calendar_groups = policy.get("calendar_groups") or {}
    local_connector = str(policy.get("local_authority_connector") or "orthodox_jordan_daily")
    internal_status = str(internal.get("reference_status") or "")
    fields = {}
    errors: list[str] = []
    warnings: list[str] = []
    for kind in ("epistle", "gospel"):
        field_name = f"{kind}_reference"
        comparison = compare_reference(
            field_name,
            published_reference(day_payload, kind),
            internal_reference(internal, kind),
            internal_status,
            observations,
            calendar_groups,
            local_connector,
        )
        comparison["native_text_evidence"] = reading_evidence(day_payload, kind)
        fields[field_name] = comparison
        errors.extend(comparison["errors"])
        warnings.extend(comparison["warnings"])

    feast = feast_texts(day_payload)
    local_status = str((local or {}).get("verification_status") or "")
    if local_status in {"LOCAL_OFFICIAL_SOURCE_VERIFIED", "LAST_VERIFIED_LOCAL_RECORD"}:
        local_commemorations = (local or {}).get("commemorations") or {}
        if generic_feast(feast):
            errors.append("verified local commemoration exists but published feast remains generic")
        commemoration_status = "VERIFIED_LOCAL_PRESENT"
    else:
        local_commemorations = {}
        commemoration_status = "NO_VERIFIED_LOCAL_RECORD"
        if generic_feast(feast):
            warnings.append("daily commemoration remains on the truthful internal fallback")

    selection = day_payload.get("liturgy_service_selection") or {}
    internal_selection = internal.get("liturgy_service_selection") or {}
    if internal_selection and selection:
        internal_type = str(internal_selection.get("service_type") or "")
        published_type = str(selection.get("service_type") or "")
        if internal_type and published_type and internal_type != published_type:
            errors.append(f"appointed liturgy conflict: {published_type} != internal {internal_type}")
    if selection.get("wrong_liturgy_fallback_allowed") is not False:
        errors.append("wrong-rite fallback is not explicitly forbidden")

    field_statuses = {item.get("status") for item in fields.values()}
    if errors:
        decision = "BLOCK_AUTOMATED_CONFLICT"
        confidence = 0.0
    elif "CONFIRMED_MULTI_SOURCE" in field_statuses:
        decision = "PUBLISH_AUTOMATED_MULTI_SOURCE"
        confidence = 0.92
    elif "CONFIRMED_AUTHORITY" in field_statuses:
        decision = "PUBLISH_AUTOMATED_AUTHORITY"
        confidence = 0.86
    else:
        decision = "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE"
        confidence = 0.72

    return {
        "date_iso": target.isoformat(),
        "decision": decision,
        "confidence": confidence,
        "human_review_required": False,
        "calendar_authority": "jerusalem_old_calendar",
        "fields": fields,
        "commemorations": {
            "status": commemoration_status,
            "published": feast,
            "verified_local": local_commemorations,
            "source_records": (local or {}).get("sources") or [],
        },
        "fasting": {
            "published": day_payload.get("fasting") or day_payload.get("fast") or {},
            "internal": internal.get("fasting") or {},
        },
        "liturgy_service_selection": {
            "published": selection,
            "internal": internal_selection,
        },
        "observations": observations,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }


def structure_drift(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_by_id = {str(item.get("connector_id") or ""): item for item in previous}
    changes = []
    for item in current:
        connector_id = str(item.get("connector_id") or "")
        old = previous_by_id.get(connector_id)
        if not old:
            continue
        old_status = str(old.get("status") or "")
        new_status = str(item.get("status") or "")
        old_hash = str(old.get("content_sha256") or "")
        new_hash = str(item.get("content_sha256") or "")
        severity = "info"
        reason = "content_changed"
        if old_status in {"current", "available", "partial"} and new_status in {
            "poisoned", "parser_error", "unusable", "http_error", "network_error"
        }:
            severity = "high"
            reason = "previously_usable_source_degraded"
        elif old_hash and new_hash and old_hash != new_hash:
            severity = "info"
        elif old_status == new_status:
            continue
        changes.append(
            {
                "connector_id": connector_id,
                "severity": severity,
                "reason": reason,
                "previous_status": old_status,
                "current_status": new_status,
                "previous_sha256": old_hash or None,
                "current_sha256": new_hash or None,
            }
        )
    return changes


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Automated liturgical source comparison",
        "",
        f"- Window: `{payload['start_date']}` → `{payload['end_date']}`",
        f"- Days: `{payload['day_count']}`",
        f"- Overall decision: **{payload['summary']['decision']}**",
        f"- Human review required: `{str(payload['human_review_required']).lower()}`",
        "",
        "| Date | Decision | Confidence | Warnings | Errors |",
        "|---|---|---:|---:|---:|",
    ]
    for item in payload["days"]:
        lines.append(
            f"| {item['date_iso']} | {item['decision']} | {item['confidence']:.2f} | "
            f"{len(item['warnings'])} | {len(item['errors'])} |"
        )
    if payload.get("source_drift"):
        lines.extend(["", "## Source drift", ""])
        for item in payload["source_drift"]:
            lines.append(
                f"- `{item['connector_id']}`: {item['previous_status']} → {item['current_status']} "
                f"({item['severity']})"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--daily", default="data/calendar/today.json")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--previous-root", type=Path)
    parser.add_argument("--attach", action="store_true", help="Attach the automated decision to the daily package.")
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date)
    day_count = resolve_day_count(args.days)
    daily_path = ROOT / args.daily
    daily = load_json(daily_path, {})
    days = package_days(daily, start, day_count)
    policy = load_json(POLICY_PATH, {})
    registry_policy, connectors = load_registry()
    by_id = {item.id: item for item in connectors}
    internal_by_date = internal_records()
    local_by_date = local_records()
    network = policy.get("network") or {}
    addressable = [
        by_id[connector_id]
        for connector_id in policy.get("date_addressable_connectors") or []
        if connector_id in by_id
    ]

    anchor = anchor_observations()
    current_anchor = [normalize_observation_dict(item) for item in anchor]
    day_results = []
    live_observations_by_date: dict[str, list[dict[str, Any]]] = {}
    fetch_cache: dict[str, tuple[int, bytes, str]] | None = {} if network.get("cache_same_url_within_run") else None

    for offset, day_payload in enumerate(days):
        target = start + timedelta(days=offset)
        observations = list(current_anchor) if offset == 0 else []
        observations.extend(source_evidence_observations(day_payload))
        for definition in addressable:
            observation = observe_with_retries(
                definition,
                target,
                offline=args.offline,
                fixture_dir=args.fixture_dir,
                attempts=int(network.get("attempts", 3)),
                initial_backoff=int(network.get("initial_backoff_seconds", 1)),
                maximum_backoff=int(network.get("maximum_backoff_seconds", 4)),
                fetch_cache=fetch_cache,
            )
            observations.append(normalize_observation_dict(asdict(observation)))
        # Deduplicate exact connector+date+reference evidence while keeping payload evidence.
        dedup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for item in observations:
            key = (
                str(item.get("connector_id") or ""),
                str(item.get("target_date") or target.isoformat()),
                normalize_reference(str(item.get("epistle_reference") or "")),
                normalize_reference(str(item.get("gospel_reference") or "")),
            )
            dedup[key] = item
        observations = list(dedup.values())
        live_observations_by_date[target.isoformat()] = observations
        result = day_decision(
            day_payload,
            target,
            observations,
            internal_by_date.get(target.isoformat(), {}),
            local_by_date.get(target.isoformat()),
            policy,
        )
        day_results.append(result)
        print(
            f"SOURCE_COMPARE date={target.isoformat()} decision={result['decision']} "
            f"confidence={result['confidence']:.2f} warnings={len(result['warnings'])} errors={len(result['errors'])}",
            flush=True,
        )

    previous_observations: list[dict[str, Any]] = []
    if args.previous_root:
        previous_path = args.previous_root / "data/sources/health/current.json"
        previous_payload = load_json(previous_path, {"observations": []})
        previous_observations = [
            normalize_observation_dict(item)
            for item in previous_payload.get("observations") or []
            if isinstance(item, dict)
        ]
    drift = structure_drift(current_anchor, previous_observations)

    blocked = [item for item in day_results if item["decision"] == "BLOCK_AUTOMATED_CONFLICT"]
    decisions = {item["decision"] for item in day_results}
    if blocked:
        overall = "BLOCK_AUTOMATED_CONFLICT"
    elif decisions == {"PUBLISH_AUTOMATED_MULTI_SOURCE"}:
        overall = "PUBLISH_AUTOMATED_MULTI_SOURCE"
    elif "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE" in decisions:
        overall = "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE"
    else:
        overall = "PUBLISH_AUTOMATED_AUTHORITY"

    payload = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=day_count - 1)).isoformat(),
        "day_count": day_count,
        "jurisdiction": registry_policy.get("jurisdiction"),
        "decision_mode": policy.get("decision_mode"),
        "human_review_required": False,
        "summary": {
            "decision": overall,
            "blocked_days": len(blocked),
            "multi_source_days": sum(item["decision"] == "PUBLISH_AUTOMATED_MULTI_SOURCE" for item in day_results),
            "authority_days": sum(item["decision"] == "PUBLISH_AUTOMATED_AUTHORITY" for item in day_results),
            "internal_failsafe_days": sum(item["decision"] == "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE" for item in day_results),
            "warning_count": sum(len(item["warnings"]) for item in day_results),
            "error_count": sum(len(item["errors"]) for item in day_results),
        },
        "source_drift": drift,
        "days": day_results,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUTPUT_DIR / f"{start.isoformat()}.json"
    current = OUTPUT_DIR / "current.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated.write_text(text, encoding="utf-8")
    current.write_text(text, encoding="utf-8")
    (OUTPUT_DIR / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, ASSET_PATH)

    if args.attach:
        summary = {
            "schema_version": 1,
            "decision": overall,
            "human_review_required": False,
            "report_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "report_asset": "data/source_comparison.json",
            "generated_at_utc": payload["generated_at_utc"],
        }
        updated = load_json(daily_path, {})
        updated["automated_source_comparison"] = summary
        for index, member in enumerate(updated.get("weekly_days") or []):
            if isinstance(member, dict) and index + 1 < len(day_results):
                member["automated_source_decision"] = {
                    "decision": day_results[index + 1]["decision"],
                    "confidence": day_results[index + 1]["confidence"],
                    "human_review_required": False,
                }
        daily_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        dated_daily = ROOT / "data" / "calendar" / f"{start.isoformat()}.json"
        if dated_daily.is_file():
            dated_daily.write_bytes(daily_path.read_bytes())

    if blocked:
        for item in blocked:
            for error in item["errors"]:
                print(f"SOURCE_COMPARE_ERROR date={item['date_iso']} {error}")
        raise SystemExit(f"SOURCE_COMPARISON_BLOCKED days={len(blocked)}")
    print(
        f"SOURCE_COMPARISON_OK start={start.isoformat()} days={day_count} decision={overall} "
        f"warnings={payload['summary']['warning_count']} drift={len(drift)}"
    )


if __name__ == "__main__":
    main()
