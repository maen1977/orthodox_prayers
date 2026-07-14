#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "canonical/content_review_status.json"
ALLOWED = {
    "automatic_official_source_verified",
    "automatic_pinned_exact_text_verified",
    "blocked_missing_official_source",
    "automatic_verified_dynamic_with_pinned_static",
}
PUBLISHABLE = {
    "automatic_official_source_verified",
    "automatic_pinned_exact_text_verified",
    "automatic_verified_dynamic_with_pinned_static",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path.relative_to(ROOT)} must contain an object")
    return value


def ids_from(path: Path) -> set[str]:
    data = load(path)
    return {
        str(item.get("id"))
        for item in data.get("services", [])
        if isinstance(item, dict) and item.get("id")
    }


def main() -> None:
    register = load(REGISTER)
    policy = register.get("policy")
    if not isinstance(policy, dict):
        raise SystemExit("content verification register has no policy object")
    if "no daily human reviewer" not in str(policy.get("meaning") or "").lower():
        raise SystemExit("content verification policy must explicitly disable daily human review")
    entries = register.get("services")
    if not isinstance(entries, dict):
        raise SystemExit("content verification register has no services object")
    expected = ids_from(ROOT / "app/src/main/assets/data/library.json") | ids_from(
        ROOT / "data/calendar/today.json"
    )
    missing = sorted(expected - set(entries))
    extra = sorted(set(entries) - expected)
    if missing:
        raise SystemExit("Missing content verification entries: " + ", ".join(missing))
    if extra:
        raise SystemExit("Stale content verification entries: " + ", ".join(extra))
    for service_id, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("status") not in ALLOWED:
            raise SystemExit(f"Invalid automatic verification status for {service_id}")
        if entry.get("status") in PUBLISHABLE and not str(entry.get("evidence") or "").strip():
            raise SystemExit(f"Publishable service {service_id} requires machine-verifiable evidence")
        if entry.get("status") == "blocked_missing_official_source":
            raise SystemExit(f"Blocked service {service_id} must not be included in published data")
    print(f"Automatic content verification register passed for {len(expected)} services")


if __name__ == "__main__":
    main()
