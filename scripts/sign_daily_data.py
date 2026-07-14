#!/usr/bin/env python3
"""Sign exact daily JSON bytes, including the dated fallback used by Android."""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data/calendar/today.json"
ASSET = ROOT / "app/src/main/assets/data/today.json"
CANONICAL_SIG = ROOT / "data/calendar/today.json.sig"
ASSET_SIG = ROOT / "app/src/main/assets/data/today.json.sig"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def daily_date() -> str:
    try:
        payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(f"Cannot parse canonical daily JSON: {error}") from error
    value = str(payload.get("date_iso") or payload.get("date") or "").strip()
    if len(value) != 10:
        raise SystemExit("Canonical daily JSON has no valid date_iso")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-key", required=True, type=Path)
    args = parser.parse_args()

    if not args.private_key.is_file():
        raise SystemExit("Private key was not found")
    if CANONICAL.read_bytes() != ASSET.read_bytes():
        raise SystemExit("Canonical and embedded daily data differ; refusing to sign")
    if shutil.which("openssl") is None:
        raise SystemExit("OpenSSL is required")

    date_iso = daily_date()
    dated_json = ROOT / f"data/calendar/{date_iso}.json"
    dated_sig = ROOT / f"data/calendar/{date_iso}.json.sig"
    if not dated_json.is_file():
        raise SystemExit(f"Dated daily JSON is missing: {dated_json}")
    if dated_json.read_bytes() != CANONICAL.read_bytes():
        raise SystemExit("Dated and today JSON differ; refusing to sign")

    with tempfile.TemporaryDirectory(prefix="orthodox-sign-") as temp:
        raw_signature = Path(temp) / "today.sig.bin"
        run([
            "openssl", "dgst", "-sha256", "-sign", str(args.private_key),
            "-out", str(raw_signature), str(CANONICAL),
        ])
        encoded = base64.b64encode(raw_signature.read_bytes()) + b"\n"
        CANONICAL_SIG.write_bytes(encoded)
        ASSET_SIG.write_bytes(encoded)
        dated_sig.write_bytes(encoded)

    print(f"Daily data signed for today alias, Android asset, and dated fallback {date_iso}")


if __name__ == "__main__":
    main()
