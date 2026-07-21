#!/usr/bin/env python3
"""Collect a best-effort, auditable health snapshot from official source connectors."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import date
from pathlib import Path

from source_connectors import ROOT, load_registry, observe_connector, probe_service_links, summarize_health

OUTPUT_DIR = ROOT / "data" / "sources" / "health"
ASSET = ROOT / "app" / "src" / "main" / "assets" / "data" / "source_health.json"


def fixture_for(fixture_dir: Path, connector_id: str) -> bytes | None:
    for suffix in (".html", ".json", ".txt"):
        candidate = fixture_dir / f"{connector_id}{suffix}"
        if candidate.is_file():
            return candidate.read_bytes()
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--offline", action="store_true", help="Do not access the network; use fixtures or write offline statuses.")
    args = parser.parse_args()
    target = date.fromisoformat(args.date)
    policy, connectors = load_registry()
    observations = []
    for connector in connectors:
        raw = fixture_for(args.fixture_dir, connector.id) if args.fixture_dir else None
        if args.offline and raw is None:
            observation = observe_connector(connector, target, raw=b"<html><body>offline fixture unavailable</body></html>")
            observation.status = "offline_not_checked"
            observation.confidence = 0.0
            observation.reason = "network disabled and no fixture supplied"
        else:
            observation = observe_connector(connector, target, raw=raw)
            if connector.parser == "dcs_service_probe" and raw is None and not args.offline:
                observation = probe_service_links(observation, connector)
        observations.append(observation)
        print(f"SOURCE_HEALTH connector={connector.id} status={observation.status} confidence={observation.confidence:.2f}")

    payload = {
        "schema_version": 1,
        "date_iso": target.isoformat(),
        "policy": policy,
        "summary": summarize_health(observations),
        "observations": [item.as_dict() for item in observations],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = OUTPUT_DIR / f"{target.isoformat()}.json"
    current = OUTPUT_DIR / "current.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated.write_text(text, encoding="utf-8")
    current.write_text(text, encoding="utf-8")
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, ASSET)

    retention = int(policy.get("health_snapshot_retention_days", 30))
    dated_files = sorted(path for path in OUTPUT_DIR.glob("????-??-??.json") if path.is_file())
    for stale in dated_files[:-retention]:
        stale.unlink(missing_ok=True)
    print(f"SOURCE_HEALTH_OK date={target.isoformat()} connectors={len(observations)} usable={payload['summary']['usable_connector_count']}")


if __name__ == "__main__":
    main()
