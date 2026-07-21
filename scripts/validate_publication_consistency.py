#!/usr/bin/env python3
"""Fail closed when aliases, embedded data, or language lanes disagree on the published day."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")


def load(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing publication file: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(f"invalid JSON in {path.relative_to(ROOT)}: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    parser.add_argument("--unsigned", action="store_true")
    args = parser.parse_args()

    today = ROOT / "data/calendar/today.json"
    dated = ROOT / f"data/calendar/{args.expected_date}.json"
    asset = ROOT / "app/src/main/assets/data/today.json"
    for path in (today, dated, asset):
        if load(path).get("date_iso") != args.expected_date:
            raise SystemExit(f"published date mismatch: {path.relative_to(ROOT)}")
    if today.read_bytes() != dated.read_bytes() or today.read_bytes() != asset.read_bytes():
        raise SystemExit("today, dated, and embedded calendar payloads must be byte-identical")

    calendar_directory = ROOT / "data/calendar"
    calendar_json = {path.name for path in calendar_directory.glob("*.json")}
    expected_calendar = {"today.json", f"{args.expected_date}.json"}
    if calendar_json != expected_calendar:
        raise SystemExit(f"unexpected calendar aliases: {sorted(calendar_json)}")
    calendar_signatures = {path.name for path in calendar_directory.glob("*.json.sig")}
    expected_signatures = set() if args.unsigned else {f"{name}.sig" for name in expected_calendar}
    if calendar_signatures != expected_signatures:
        raise SystemExit(f"unexpected calendar signatures: {sorted(calendar_signatures)}")

    lanes = []
    for language in LANGUAGES:
        lane_dated = ROOT / f"data/daily/{args.expected_date}/{language}.json"
        lane_current = ROOT / f"data/daily/current/{language}.json"
        if not lane_dated.exists() and not lane_current.exists():
            continue
        data = load(lane_dated)
        current = load(lane_current)
        if data.get("date_iso") != args.expected_date or current.get("date_iso") != args.expected_date:
            raise SystemExit(f"language lane date mismatch: {language}")
        if data.get("language") != language or current.get("language") != language:
            raise SystemExit(f"language lane identifier mismatch: {language}")
        if lane_dated.read_bytes() != lane_current.read_bytes():
            raise SystemExit(f"dated/current lane bytes differ: {language}")
        lanes.append(language)

    if not lanes:
        raise SystemExit("no language lane is publishable")

    payloads = [today, dated, asset]
    for language in lanes:
        payloads.extend([
            ROOT / f"data/daily/{args.expected_date}/{language}.json",
            ROOT / f"data/daily/current/{language}.json",
        ])
    for payload in payloads:
        signature = Path(str(payload) + ".sig")
        if args.unsigned and signature.exists():
            raise SystemExit(f"stale signature beside unsigned payload: {signature.relative_to(ROOT)}")
        if not args.unsigned and not signature.is_file():
            raise SystemExit(f"missing signature: {signature.relative_to(ROOT)}")

    print(f"PUBLICATION_CONSISTENCY_OK date={args.expected_date} lanes={','.join(lanes)} unsigned={args.unsigned}")


if __name__ == "__main__":
    main()
