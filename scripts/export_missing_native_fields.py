#!/usr/bin/env python3
"""Export a review checklist for missing English/Greek native service fields."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def walk(value: Any, language: str, pointer: str = ""):
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            if not str(value.get(language) or "").strip():
                yield pointer
        else:
            for key, child in value.items():
                next_pointer = f"{pointer}.{key}" if pointer else key
                yield from walk(child, language, next_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, language, f"{pointer}[{index}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=("en", "el"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pack_path = ROOT / "data/services/native" / f"library_{args.language}.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "language": args.language,
        "policy": "ORIGINAL_OFFICIAL_TEXT_ONLY_NO_TRANSLATION",
        "coverage": pack.get("native_content_status", {}),
        "services": [],
    }
    for service in pack.get("services", []):
        missing = list(walk(service, args.language))
        if not missing:
            continue
        source = service.get("native_source", {})
        report["services"].append({
            "id": service.get("id"),
            "source_id": source.get("source_id"),
            "source_url": source.get("url"),
            "missing_count": len(missing),
            "missing_fields": missing,
        })
    output = args.output or Path("docs") / f"native_missing_{args.language}.json"
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)} with {sum(item['missing_count'] for item in report['services'])} missing fields")


if __name__ == "__main__":
    main()
