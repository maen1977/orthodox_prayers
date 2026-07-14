#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    raise SystemExit("Install development requirements: pip install -r requirements-dev.txt") from exc
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/daily_data.schema.json").read_text(encoding="utf-8"))

def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        for error in errors:
            location = "/".join(map(str, error.absolute_path)) or "<root>"
            print(f"::error file={path},title=Daily data schema::{location}: {error.message}")
        raise SystemExit(1)
    print(f"Schema validation passed: {path.relative_to(ROOT)}")

if __name__ == "__main__":
    targets = [Path(value) for value in sys.argv[1:]] or [ROOT / "data/calendar/today.json", ROOT / "app/src/main/assets/data/today.json"]
    for target in targets:
        validate(target if target.is_absolute() else ROOT / target)
