"""Attach the project owner's explicit republication attestation to existing daily proper sources.

This changes metadata only. It never creates a source, fills a missing source,
or edits any native-language text. A URL alone remains insufficient; every
annotated source receives an explicit project-owner authorization reference.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATTESTATION = "USER_CONFIRMED_REPUBLICATION_PERMISSION_FOR_ORTHODOX_DAILY_PROPERS_SOURCES_2026_08_24"
FILES = (
    "canonical/daily_propers.json",
    "canonical/dated_liturgical_propers.json",
    "canonical/paschal_cycle_propers.json",
    "canonical/resurrectional_propers.json",
)
TEXT_KEYS = {"troparion", "kontakion", "communion", "prokeimenon", "name", "body", "title", "reference"}


def annotate_source(source: Any) -> int:
    if not isinstance(source, dict):
        return 0
    if not str(source.get("source_id") or "").strip() or not str(source.get("url") or "").strip():
        return 0
    source.update(
        {
            "permission_confirmed": True,
            "redistribution_review_required": False,
            "permission_basis": "CONFIRMED_BY_PROJECT_OWNER",
            "authorization_reference": ATTESTATION,
            "machine_translation_used": False,
        }
    )
    return 1


def annotate_daily(data: dict) -> int:
    count = 0
    for entry in (data.get("fixed_feasts") or {}).values():
        for source in (entry.get("sources") or {}).values():
            count += annotate_source(source)
    for source in (data.get("weekly_sources") or {}).values():
        count += annotate_source(source)
    return count


def annotate_dated(data: dict) -> int:
    count = 0
    for entry in (data.get("dates") or {}).values():
        for source in (entry.get("sources") or {}).values():
            count += annotate_source(source)
    return count


def annotate_paschal(data: dict) -> int:
    count = 0
    for entry in (data.get("offsets") or {}).values():
        for source in (entry.get("sources") or {}).values():
            count += annotate_source(source)
    return count


def annotate_resurrectional(data: dict) -> int:
    count = 0
    for source in (data.get("sources") or {}).values():
        count += annotate_source(source)
    return count


def text_projection(value: Any) -> Any:
    """Project all likely native text nodes for a before/after immutability check."""
    if isinstance(value, dict):
        return {
            key: text_projection(node)
            for key, node in value.items()
            if key in TEXT_KEYS or isinstance(node, (dict, list))
        }
    if isinstance(value, list):
        return [text_projection(node) for node in value]
    return value


def main() -> None:
    total = 0
    for relative in FILES:
        path = ROOT / relative
        data = json.loads(path.read_text(encoding="utf-8"))
        before = copy.deepcopy(text_projection(data))
        if relative.endswith("daily_propers.json"):
            total += annotate_daily(data)
        elif relative.endswith("dated_liturgical_propers.json"):
            total += annotate_dated(data)
        elif relative.endswith("paschal_cycle_propers.json"):
            total += annotate_paschal(data)
        elif relative.endswith("resurrectional_propers.json"):
            total += annotate_resurrectional(data)
        after = text_projection(data)
        if before != after:
            raise SystemExit(f"native text changed unexpectedly in {relative}")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"annotated_sources={total} attestation={ATTESTATION}")


if __name__ == "__main__":
    main()
