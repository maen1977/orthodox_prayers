#!/usr/bin/env python3
"""Recompose daily service overlays after exact native Scripture has been filled.

The first calendar-generation pass builds services before native Scripture corpora
are resolved. Rebuilding here ensures the Divine Liturgy and other service
placeholders contain the same verified Epistle/Gospel text shown by Readings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_text_contract import ROOT
from orthodox_integrity import rebuild_services


def process(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    today_readings = data.get("readings")
    next_payload = data.get("integrity_inputs", {}).get("next_sunday", {})
    next_readings = next_payload.get("readings") if isinstance(next_payload, dict) else None
    if not isinstance(today_readings, list):
        raise ValueError(f"{path}: missing readings")
    if not isinstance(next_readings, list):
        raise ValueError(f"{path}: missing integrity_inputs.next_sunday.readings")
    rebuild_services(data, today_readings, next_readings)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=["data/calendar/today.json"])
    args = parser.parse_args()
    for raw_path in args.paths:
        path = ROOT / raw_path
        process(path)
        print(f"Rebuilt verified daily service overlays in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
