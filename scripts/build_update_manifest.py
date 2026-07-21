#!/usr/bin/env python3
"""Build the small signed manifest consumed before downloading daily payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
OUTPUT = ROOT / "data/update-manifest.json"


def configured_minimum_app_version_code() -> int:
    contract_path = ROOT / "canonical/update_contract.json"
    if contract_path.is_file():
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except Exception as error:
            raise SystemExit(f"invalid update contract: {error}") from error
        if contract.get("manifest_schema_version") != 1:
            raise SystemExit("update contract manifest schema mismatch")
        value = contract.get("minimum_app_version_code")
        if isinstance(value, int) and value > 0:
            return value
        raise SystemExit("invalid minimum app version in update contract")
    # Compatibility fallback for a stripped publication worktree assembled by an
    # older workflow. The current workflow copies update_contract.json explicitly.
    if OUTPUT.is_file():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
            value = existing.get("minimum_app_version_code")
            if isinstance(value, int) and value > 0:
                return value
        except Exception:
            pass
    raise SystemExit("could not derive minimum app version code")


def file_entry(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "signature_path": path.relative_to(ROOT).as_posix() + ".sig",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--revision", type=int, default=int(os.environ.get("GITHUB_RUN_NUMBER", "1")))
    parser.add_argument("--minimum-app-version-code", type=int)
    parser.add_argument("--published-at-utc")
    args = parser.parse_args()

    if args.revision < 1:
        raise SystemExit("manifest revision must be positive")
    calendar = ROOT / "data/calendar/today.json"
    if not calendar.is_file():
        raise SystemExit("canonical today.json is missing")
    calendar_data = json.loads(calendar.read_text(encoding="utf-8"))
    if calendar_data.get("date_iso") != args.date:
        raise SystemExit("canonical today.json date does not match manifest date")

    languages: dict[str, object] = {}
    for language in LANGUAGES:
        dated = ROOT / f"data/daily/{args.date}/{language}.json"
        current = ROOT / f"data/daily/current/{language}.json"
        if not dated.exists() and not current.exists():
            continue
        if not dated.is_file() or not current.is_file():
            raise SystemExit(f"incomplete language lane: {language}")
        if dated.read_bytes() != current.read_bytes():
            raise SystemExit(f"dated/current language lane mismatch: {language}")
        payload = json.loads(dated.read_text(encoding="utf-8"))
        if payload.get("date_iso") != args.date or payload.get("language") != language:
            raise SystemExit(f"invalid language lane metadata: {language}")
        entry = file_entry(dated)
        entry["current_path"] = current.relative_to(ROOT).as_posix()
        entry["current_signature_path"] = current.relative_to(ROOT).as_posix() + ".sig"
        languages[language] = entry

    if not languages:
        raise SystemExit("no language lanes are available for the manifest")

    published_at = args.published_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    minimum_app_version_code = (
        args.minimum_app_version_code
        if args.minimum_app_version_code is not None
        else configured_minimum_app_version_code()
    )
    if minimum_app_version_code < 1:
        raise SystemExit("minimum app version code must be positive")
    manifest = {
        "manifest_schema_version": 1,
        "date_iso": args.date,
        "revision": args.revision,
        "published_at_utc": published_at,
        "minimum_app_version_code": minimum_app_version_code,
        "calendar": file_entry(calendar),
        "languages": languages,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"UPDATE_MANIFEST_BUILT date={args.date} revision={args.revision} lanes={','.join(languages)}")


if __name__ == "__main__":
    main()
