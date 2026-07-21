#!/usr/bin/env python3
"""Validate source connector, health, directory, and truthful coverage contracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from source_connectors import ROOT, load_registry, normalize_reference
from attach_source_intelligence import coverage as build_coverage


def https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("daily", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--expected-date")
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
    expected = args.expected_date or daily.get("date_iso")
    health = daily.get("source_health") or json.loads((ROOT / "data/sources/health/current.json").read_text(encoding="utf-8"))
    if health.get("date_iso") != expected:
        raise SystemExit("daily source-health date mismatch")
    observations = health.get("observations") or []
    if len(observations) != len(connectors):
        raise SystemExit("daily source-health connector count mismatch")
    if {item.get("connector_id") for item in observations} != set(ids):
        raise SystemExit("daily source-health connector IDs mismatch")
    for item in observations:
        if not https(str(item.get("url") or "")):
            raise SystemExit(f"{item.get('connector_id')}: observation URL must be HTTPS")
        if "full text" in str(item.get("rights_mode") or "").lower() and "restricted" not in str(item.get("rights_mode") or "").lower():
            pass

    directory = daily.get("church_directory") or json.loads((ROOT / "data/directory/churches.json").read_text(encoding="utf-8"))
    if directory.get("authority") != "orthodox_jordan" or not https(str(directory.get("directory_url") or "")):
        raise SystemExit("official Jordan church directory contract is missing")
    churches = directory.get("churches") or []
    if len(churches) < 5 or directory.get("count") != len(churches):
        raise SystemExit("church directory is incomplete or count is inconsistent")
    for church in churches:
        if not str((church.get("name") or {}).get("ar") or "").strip() or not https(str(church.get("url") or "")):
            raise SystemExit("church directory entry is incomplete")

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
    print(f"Source intelligence validated: {len(connectors)} connectors, {len(churches)} church links")


if __name__ == "__main__":
    main()
