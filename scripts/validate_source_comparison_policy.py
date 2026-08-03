#!/usr/bin/env python3
"""Validate the automatic source-research policy and connector registry."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "canonical/source_comparison_policy.json"
REGISTRY = ROOT / "canonical/source_connectors.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if policy.get("visible_window_days") != 9:
        fail("source comparison policy must cover exactly nine visible days")
    if policy.get("human_review_required") is not False:
        fail("source comparison policy must not depend on human review")
    if policy.get("decision_mode") != "AUTOMATED_FAIL_CLOSED":
        fail("source comparison must be automated and fail closed")
    decisions = set(policy.get("publication_decisions") or [])
    required = {
        "PUBLISH_AUTOMATED_MULTI_SOURCE",
        "PUBLISH_AUTOMATED_AUTHORITY",
        "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE",
        "BLOCK_AUTOMATED_CONFLICT",
    }
    if decisions != required:
        fail(f"unexpected source comparison decisions: {sorted(decisions)}")
    connectors = registry.get("connectors") or []
    ids = {str(item.get("id")) for item in connectors}
    for connector_id in policy.get("date_addressable_connectors") or []:
        if connector_id not in ids:
            fail(f"date-addressable connector is missing: {connector_id}")
    if str(policy.get("local_authority_connector")) not in ids:
        fail("local authority connector is missing")
    if len(connectors) < 10:
        fail("at least ten official/fallback connectors are required")
    if not all(item.get("official") is True for item in connectors):
        fail("every registered external source must be explicitly official")
    for item in connectors:
        if int(item.get("retry_attempts") or 0) < 2:
            fail(f"connector retries are too weak: {item.get('id')}")
        if not item.get("calendar_profile"):
            fail(f"connector calendar profile is missing: {item.get('id')}")
        if not item.get("rights_mode"):
            fail(f"connector rights mode is missing: {item.get('id')}")
    if registry.get("policy", {}).get("human_review_required") is not False:
        fail("connector registry still depends on human review")
    print(
        "SOURCE_COMPARISON_POLICY_OK days=9 mode=AUTOMATED_FAIL_CLOSED "
        f"connectors={len(connectors)} human_review=false"
    )


if __name__ == "__main__":
    main()
