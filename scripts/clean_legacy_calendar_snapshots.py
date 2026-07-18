#!/usr/bin/env python3
"""Remove obsolete top-level calendar snapshots while preserving today's signed pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clean(repository_root: Path, dry_run: bool = False) -> list[Path]:
    calendar_dir = repository_root / "data" / "calendar"
    today_path = calendar_dir / "today.json"
    if not today_path.is_file():
        raise SystemExit(f"Missing required file: {today_path}")

    payload = json.loads(today_path.read_text(encoding="utf-8"))
    date_iso = payload.get("date_iso")
    if not isinstance(date_iso, str) or not date_iso:
        raise SystemExit("data/calendar/today.json has no valid date_iso")

    keep = {
        "today.json",
        "today.json.sig",
        f"{date_iso}.json",
        f"{date_iso}.json.sig",
    }

    removed: list[Path] = []
    for path in sorted(calendar_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in {".json", ".sig"}:
            continue
        if path.name in keep:
            continue
        if path.name.endswith(".json.sig") or path.suffix == ".json":
            removed.append(path)
            if not dry_run:
                path.unlink()

    action = "WOULD_REMOVE" if dry_run else "REMOVED"
    for path in removed:
        print(f"{action} {path.relative_to(repository_root)}")
    print(f"CALENDAR_CLEAN_OK date={date_iso} removed={len(removed)} dry_run={str(dry_run).lower()}")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    clean(args.root.resolve(), args.dry_run)


if __name__ == "__main__":
    main()
