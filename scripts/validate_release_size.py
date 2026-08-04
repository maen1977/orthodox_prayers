#!/usr/bin/env python3
"""Fail release packaging when generated artifacts exceed the lightweight app budget."""
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--aab", type=Path)
    parser.add_argument("--source-zip", type=Path)
    parser.add_argument("--budgets", type=Path, default=ROOT / "config/release-size-budgets.json")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    budget = json.loads(args.budgets.read_text(encoding="utf-8"))
    specs = [("apk", args.apk, "apk_bytes_max"), ("aab", args.aab, "aab_bytes_max"), ("source_zip", args.source_zip, "source_zip_bytes_max")]
    result = {"schema_version": 1, "status": "PASS", "artifacts": {}}
    failures = []
    for name, path, key in specs:
        if path is None:
            continue
        if not path.is_file():
            raise SystemExit(f"Missing {name}: {path}")
        size = path.stat().st_size
        maximum = int(budget[key])
        result["artifacts"][name] = {"path": str(path), "bytes": size, "max_bytes": maximum}
        if size > maximum:
            failures.append(f"{name} size {size} exceeds {maximum}")
    if failures:
        result["status"] = "FAIL"; result["failures"] = failures
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("RELEASE_SIZE_" + result["status"] + " " + " ".join(f"{k}={v['bytes']}" for k,v in result["artifacts"].items()))
    if failures:
        raise SystemExit("; ".join(failures))

if __name__ == "__main__": main()
