#!/usr/bin/env python3
"""Validate source connector, health, directory, and truthful coverage contracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from source_connectors import ROOT, load_registry, normalize_reference
from attach_source_intelligence import coverage as build_coverage


def https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_church_directory(
    directory: dict[str, Any],
    language: str,
    *,
    strict_reviewed_names: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if directory.get("authority") != "orthodox_jordan" or not https(str(directory.get("directory_url") or "")):
        raise SystemExit("official Jordan church directory contract is missing")
    churches = directory.get("churches") or []
    if len(churches) < 5 or directory.get("count") != len(churches):
        raise SystemExit("church directory is incomplete or count is inconsistent")

    native_name_counts = {item: 0 for item in ("ar", "en", "el")}
    for index, church in enumerate(churches):
        if not str(church.get("id") or "").strip() or not https(str(church.get("url") or "")):
            raise SystemExit(f"church directory entry is structurally incomplete at index {index}")
        if "official" in church and church.get("official") is not True:
            raise SystemExit(f"church directory entry is not official at index {index}")
        if "source_id" in church and church.get("source_id") != "orthodox_jordan":
            raise SystemExit(f"church directory entry has the wrong authority at index {index}")
        names = church.get("name") or {}
        for native_language in native_name_counts:
            if str(names.get(native_language) or "").strip():
                native_name_counts[native_language] += 1
        if language == "all" and not any(str(names.get(item) or "").strip() for item in native_name_counts):
            raise SystemExit(f"church directory entry has no verified display name at index {index}")
        if language == "ar" and not str(names.get("ar") or "").strip():
            raise SystemExit(f"church directory Arabic name is missing at index {index}")

    required_reviewed_names = min(5, len(churches))
    if language == "all":
        if native_name_counts["ar"] != len(churches):
            raise SystemExit("aggregate church directory must retain every official Arabic name")
        for native_language in ("en", "el"):
            if strict_reviewed_names and native_name_counts[native_language] < required_reviewed_names:
                raise SystemExit(
                    f"aggregate church directory lacks reviewed {native_language} names: "
                    f"{native_name_counts[native_language]}/{required_reviewed_names}"
                )
    elif language in {"en", "el"} and native_name_counts[language] < required_reviewed_names:
        raise SystemExit(
            f"church directory lacks reviewed native names for {language}: "
            f"{native_name_counts[language]}/{required_reviewed_names}"
        )
    return churches, native_name_counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("daily", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--expected-date")
    parser.add_argument("--language", choices=("all", "ar", "en", "el"))
    args = parser.parse_args()
    policy, connectors = load_registry()
    if len(connectors) < 9:
        raise SystemExit("source connector registry must contain at least nine official connectors")
    ids = [item.id for item in connectors]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate source connector id")
    if policy.get("local_authority_source_id") != "orthodox_jordan":
        raise SystemExit("Jordan must remain the local authority")
    for item in connectors:
        if not item.official or not https(item.url_template):
            raise SystemExit(f"{item.id}: connector must be official and HTTPS")
        if item.authority_tier < 1 or item.authority_tier > 5:
            raise SystemExit(f"{item.id}: invalid authority tier")
        if not item.rights_mode:
            raise SystemExit(f"{item.id}: rights mode is missing")

    path = ROOT / args.daily
    daily = json.loads(path.read_text(encoding="utf-8"))
    embedded_language = str(daily.get("language") or "").strip()
    language = args.language or embedded_language or "all"
    if embedded_language and embedded_language != language:
        raise SystemExit(f"source-intelligence language mismatch: payload={embedded_language} requested={language}")
    expected = args.expected_date or daily.get("date_iso")
    health = daily.get("source_health") or json.loads((ROOT / "data/sources/health/current.json").read_text(encoding="utf-8"))
    if health.get("date_iso") != expected:
        raise SystemExit("daily source-health date mismatch")
    observations = health.get("observations") or []
    observed_ids = {item.get("connector_id") for item in observations}
    registry_ids = set(ids)
    if args.expected_date:
        if len(observations) != len(connectors):
            raise SystemExit("daily source-health connector count mismatch")
        if observed_ids != registry_ids:
            raise SystemExit("daily source-health connector IDs mismatch")
    else:
        # A signed embedded bootstrap may predate an additive connector. It remains
        # immutable until Update republishes it. Source-tree validation accepts only
        # a complete legacy subset; dated publication validation above stays strict.
        if len(observations) < 9 or not observed_ids.issubset(registry_ids):
            raise SystemExit("embedded source-health connector set is not a safe legacy subset")
        missing = sorted(registry_ids - observed_ids)
        if missing:
            print("LEGACY_SOURCE_HEALTH_SUBSET missing=" + ",".join(missing))
    for item in observations:
        if not https(str(item.get("url") or "")):
            raise SystemExit(f"{item.get('connector_id')}: observation URL must be HTTPS")
        if "full text" in str(item.get("rights_mode") or "").lower() and "restricted" not in str(item.get("rights_mode") or "").lower():
            pass

    directory = daily.get("church_directory") or json.loads((ROOT / "data/directory/churches.json").read_text(encoding="utf-8"))
    strict_reviewed_names = bool(args.expected_date) or language != "all"
    churches, native_name_counts = validate_church_directory(
        directory,
        language,
        strict_reviewed_names=strict_reviewed_names,
    )
    if not strict_reviewed_names and any(native_name_counts[item] < min(5, len(churches)) for item in ("en", "el")):
        print(
            "LEGACY_CHURCH_DIRECTORY_LOCALIZATION_SUBSET "
            f"en={native_name_counts['en']} el={native_name_counts['el']} required_after_update={min(5, len(churches))}"
        )

    # A current local-authority observation must agree with the published reading references.
    generated = {}
    for reading in daily.get("readings") or []:
        kind = str(reading.get("kind") or "")
        if kind not in {"epistle", "gospel"}:
            continue
        reference = reading.get("reference") or {}
        value = reference.get("en") or reference.get("ar") or reference.get("el") or ""
        generated[kind + "_reference"] = normalize_reference(str(value))
    for observation in observations:
        if observation.get("connector_id") != "orthodox_jordan_daily" or observation.get("status") != "current":
            continue
        for field in ("epistle_reference", "gospel_reference"):
            observed = normalize_reference(str(observation.get(field) or ""))
            published = generated.get(field, "")
            if observed and published and not (observed == published or observed in published or published in observed):
                raise SystemExit(f"local authority conflict for {field}: {observed} != {published}")

    coverage = daily.get("service_coverage") or build_coverage(daily)
    entries = {item.get("service_id"): item for item in coverage.get("services") or []}
    liturgy = entries.get("divine_liturgy")
    if not liturgy:
        raise SystemExit("Divine Liturgy coverage declaration is missing")
    if liturgy.get("complete") is True and liturgy.get("missing_variables"):
        raise SystemExit("Divine Liturgy coverage falsely claims completeness")
    if liturgy.get("coverage_percent", 0) > 100:
        raise SystemExit("invalid service coverage percentage")
    print(
        f"Source intelligence validated: {len(connectors)} connectors, {len(churches)} church links "
        f"language={language} native_names="
        f"ar:{native_name_counts['ar']},en:{native_name_counts['en']},el:{native_name_counts['el']}"
    )


if __name__ == "__main__":
    main()
