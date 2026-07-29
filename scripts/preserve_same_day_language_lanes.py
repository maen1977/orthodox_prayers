#!/usr/bin/env python3
"""Keep the last good same-day lane when a later run is incomplete.

The 06:00 run is supplemental. It may publish a richer signed lane, but it must
never delete native text already published by the 01:00 run. If a candidate
regresses, the complete earlier lane is carried forward and signed again.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

LANGUAGES = ("ar", "en", "el")
READING_KINDS = ("matins_gospel", "prokeimenon", "epistle", "gospel")


def load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def reading_by_kind(data: dict[str, Any], kind: str) -> dict[str, Any] | None:
    for reading in data.get("readings") or []:
        if isinstance(reading, dict) and reading.get("kind") == kind:
            return reading
    return None


def protected_values(data: dict[str, Any], language: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for kind in READING_KINDS:
        reading = reading_by_kind(data, kind)
        if not reading:
            continue
        for field in ("reference", "body"):
            localized = reading.get(field)
            value = (
                str(localized.get(language) or "").strip()
                if isinstance(localized, dict)
                else ""
            )
            if value:
                values[f"reading:{kind}:{field}"] = value

    for service in data.get("services") or []:
        if not isinstance(service, dict) or service.get("id") != "divine_liturgy":
            continue
        slots = service.get("slot_replacements")
        if not isinstance(slots, dict):
            continue
        for slot, localized in slots.items():
            value = (
                str(localized.get(language) or "").strip()
                if isinstance(localized, dict)
                else ""
            )
            if value:
                values[f"slot:{slot}"] = value
    return values


def regressions(
    accepted: dict[str, Any],
    candidate: dict[str, Any],
    language: str,
) -> list[str]:
    previous = protected_values(accepted, language)
    current = protected_values(candidate, language)
    return sorted(key for key in previous if not current.get(key))


def preserve_lane(
    candidate_root: Path,
    published_root: Path,
    date_iso: str,
    language: str,
) -> str:
    candidate = candidate_root / "daily/current" / f"{language}.json"
    published = published_root / "daily/current" / f"{language}.json"
    accepted_data = load(published)
    if not accepted_data or accepted_data.get("date_iso") != date_iso:
        return "no-same-day-baseline"

    candidate_data = load(candidate)
    lost = (
        ["candidate-lane-missing"]
        if not candidate_data or candidate_data.get("date_iso") != date_iso
        else regressions(accepted_data, candidate_data, language)
    )
    if not lost:
        return "candidate-kept"

    dated = candidate_root / "daily" / date_iso / f"{language}.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    dated.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(published, candidate)
    shutil.copy2(published, dated)
    Path(str(candidate) + ".sig").unlink(missing_ok=True)
    Path(str(dated) + ".sig").unlink(missing_ok=True)
    return "previous-lane-preserved:" + ",".join(lost)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--published-root", type=Path, required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    for language in LANGUAGES:
        state = preserve_lane(
            args.candidate_root,
            args.published_root,
            args.date,
            language,
        )
        print(f"SAME_DAY_LANE language={language} state={state}")


if __name__ == "__main__":
    main()
