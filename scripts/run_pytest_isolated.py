#!/usr/bin/env python3
"""Run every project test file in deterministic isolated batches.

A few long-lived test modules intentionally mutate import/module state while
simulating repair pipelines. Running all files in one interpreter can therefore
slow down or hang late in the suite. Separate pytest processes preserve exact
coverage while making the release gate deterministic.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")

    files = sorted((ROOT / "tests").glob("test_*.py"))
    if not files:
        raise SystemExit("No tests/test_*.py files found")

    batches = [files[i:i + args.batch_size] for i in range(0, len(files), args.batch_size)]
    for index, batch in enumerate(batches, start=1):
        print(f"\nPYTEST_ISOLATED_BATCH {index}/{len(batches)} files={len(batch)}", flush=True)
        command = [sys.executable, "-m", "pytest"]
        if args.quiet:
            command.append("-q")
        command.extend(str(path.relative_to(ROOT)) for path in batch)
        subprocess.run(command, cwd=ROOT, check=True)

    print(f"PYTEST_ISOLATED_OK files={len(files)} batches={len(batches)}", flush=True)


if __name__ == "__main__":
    main()
