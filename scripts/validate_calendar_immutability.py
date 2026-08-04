#!/usr/bin/env python3
"""Fail when the approved offline calendar through 2050 changes by even one byte."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "canonical" / "calendar_2026_2050_lock.json"
EXPECTED_START = "2026-01-01"
EXPECTED_END = "2050-12-31"
EXPECTED_DAYS = 9131


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> None:
    if not LOCK.is_file():
        raise SystemExit("CALENDAR_IMMUTABILITY_ERROR missing canonical/calendar_2026_2050_lock.json")
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("policy") != "IMMUTABLE_OFFLINE_CALENDAR_2026_2050_DO_NOT_REGENERATE_OR_EDIT":
        errors.append("lock policy is missing or changed")
    civil = payload.get("civil_range") or {}
    if civil != {"start": EXPECTED_START, "end": EXPECTED_END, "day_count": EXPECTED_DAYS}:
        errors.append("locked civil range must remain 2026-01-01 through 2050-12-31")

    records = payload.get("files") or []
    locked_paths = [str(item.get("path") or "") for item in records if isinstance(item, dict)]
    if len(locked_paths) != len(set(locked_paths)):
        errors.append("lock contains duplicate file paths")

    actual_calendar_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "app/src/main/assets/data/calendar").glob("*.json")
    }
    expected_calendar_files = {
        path for path in locked_paths if path.startswith("app/src/main/assets/data/calendar/")
    }
    missing_from_lock = sorted(actual_calendar_files - expected_calendar_files)
    missing_from_tree = sorted(expected_calendar_files - actual_calendar_files)
    if missing_from_lock:
        errors.append("unlocked calendar files: " + ", ".join(missing_from_lock))
    if missing_from_tree:
        errors.append("locked calendar files were removed: " + ", ".join(missing_from_tree))

    aggregate_lines: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            errors.append("invalid lock record")
            continue
        relative = str(item.get("path") or "")
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing locked file: {relative}")
            continue
        raw = path.read_bytes()
        actual_hash = sha256_bytes(raw)
        expected_hash = str(item.get("sha256") or "")
        expected_bytes = int(item.get("bytes") or -1)
        if len(raw) != expected_bytes:
            errors.append(f"byte-size changed: {relative} expected={expected_bytes} actual={len(raw)}")
        if actual_hash != expected_hash:
            errors.append(f"SHA-256 changed: {relative} expected={expected_hash} actual={actual_hash}")
        aggregate_lines.append(f"{actual_hash}  {relative}")

    aggregate = sha256_bytes("\n".join(aggregate_lines).encode("utf-8"))
    if aggregate != str(payload.get("aggregate_sha256") or ""):
        errors.append("aggregate calendar lock hash changed")
    if int(payload.get("file_count") or -1) != len(records):
        errors.append("file_count does not match lock records")

    if errors:
        for error in errors:
            print(f"CALENDAR_IMMUTABILITY_ERROR {error}")
        raise SystemExit(1)
    print(
        "CALENDAR_IMMUTABILITY_OK "
        f"start={EXPECTED_START} end={EXPECTED_END} days={EXPECTED_DAYS} "
        f"files={len(records)} aggregate_sha256={aggregate}"
    )


if __name__ == "__main__":
    main()
