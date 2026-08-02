#!/usr/bin/env python3
"""Compare current and previously published source snapshots without changing data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def keyed(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observations = payload.get("observations") or payload.get("connectors") or []
    return {
        str(item.get("connector_id") or item.get("id")): item
        for item in observations
        if isinstance(item, dict) and (item.get("connector_id") or item.get("id"))
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    current = keyed(load(args.current))
    previous = keyed(load(args.previous))
    changes: list[dict[str, Any]] = []
    for connector_id in sorted(set(current) | set(previous)):
        now = current.get(connector_id, {})
        before = previous.get(connector_id, {})
        changed: dict[str, Any] = {}
        for field in ("status", "http_status", "structure_sha256", "content_sha256", "reason"):
            old, new = before.get(field), now.get(field)
            if old != new:
                changed[field] = {"previous": old, "current": new}
        if changed:
            changes.append({"connector_id": connector_id, "changes": changed})

    regressions = [
        item for item in changes
        if item["changes"].get("status", {}).get("current")
        in {"poisoned", "network_error", "http_error", "parser_error", "unusable"}
    ]
    result = {
        "schema_version": 1,
        "current_connector_count": len(current),
        "previous_connector_count": len(previous),
        "change_count": len(changes),
        "regression_count": len(regressions),
        "changes": changes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"SOURCE_DRIFT_OK current={len(current)} previous={len(previous)} "
        f"changes={len(changes)} regressions={len(regressions)}"
    )


if __name__ == "__main__":
    main()
