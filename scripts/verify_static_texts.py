#!/usr/bin/env python3
"""Protect the frozen liturgical baseline against accidental text changes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "canonical" / "static_hashes.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update",
        action="store_true",
        help="Intentionally replace stored hashes after reviewing a baseline change.",
    )
    args = parser.parse_args()

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise SystemExit("canonical/static_hashes.json contains no protected files")

    failures: list[str] = []
    updated: dict[str, str] = {}
    for relative, expected in files.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing protected file: {relative}")
            continue
        actual = digest(path)
        updated[relative] = actual
        if actual != expected:
            failures.append(
                f"protected text changed: {relative}\n"
                f"  expected {expected}\n"
                f"  actual   {actual}"
            )

    if args.update:
        if failures and any(item.startswith("missing") for item in failures):
            raise SystemExit("\n".join(failures))
        payload["files"] = updated
        MANIFEST.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Updated {len(updated)} protected text hashes")
        return

    if failures:
        raise SystemExit(
            "Static Orthodox text integrity check failed. "
            "Do not update hashes unless the text change is intentional.\n"
            + "\n".join(failures)
        )
    print(f"Static text integrity passed for {len(updated)} protected files")


if __name__ == "__main__":
    main()
