#!/usr/bin/env python3
"""Verify canonical, dated, and embedded daily-data signatures."""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "canonical/signing/data_signing_public_key.pub"
TODAY_JSON = ROOT / "data/calendar/today.json"
TODAY_SIG = ROOT / "data/calendar/today.json.sig"
ASSET_JSON = ROOT / "app/src/main/assets/data/today.json"
ASSET_SIG = ROOT / "app/src/main/assets/data/today.json.sig"


def verify(payload: Path, encoded_signature: Path) -> None:
    try:
        raw = base64.b64decode(encoded_signature.read_bytes().strip(), validate=True)
    except Exception as error:
        raise SystemExit(f"Invalid Base64 signature: {encoded_signature}: {error}") from error

    with tempfile.TemporaryDirectory(prefix="orthodox-verify-") as temp:
        raw_path = Path(temp) / "signature.bin"
        raw_path.write_bytes(raw)
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(PUBLIC_KEY), "-signature", str(raw_path), str(payload)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or "Verified OK" not in result.stdout:
            detail = (result.stdout + result.stderr).strip()
            raise SystemExit(f"Signature verification failed for {payload}: {detail}")


def dated_pair() -> tuple[Path, Path]:
    try:
        payload = json.loads(TODAY_JSON.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(f"Cannot parse canonical daily JSON: {error}") from error
    date_iso = str(payload.get("date_iso") or payload.get("date") or "").strip()
    if len(date_iso) != 10:
        raise SystemExit("Canonical daily JSON has no valid date_iso")
    return (
        ROOT / f"data/calendar/{date_iso}.json",
        ROOT / f"data/calendar/{date_iso}.json.sig",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", nargs="?")
    parser.add_argument("signature", nargs="?")
    args = parser.parse_args()
    if bool(args.payload) != bool(args.signature):
        parser.error("payload and signature must be supplied together")
    if shutil.which("openssl") is None:
        raise SystemExit("OpenSSL is required")
    if not PUBLIC_KEY.is_file():
        raise SystemExit("Committed public key is missing")
    if args.payload and args.signature:
        payload = Path(args.payload)
        signature = Path(args.signature)
        verify(payload, signature)
        print(f"Detached signature verified: {payload}")
        return

    dated_json, dated_sig = dated_pair()
    pairs = [(TODAY_JSON, TODAY_SIG), (ASSET_JSON, ASSET_SIG), (dated_json, dated_sig)]
    for payload, signature in pairs:
        if not payload.is_file() or not signature.is_file():
            raise SystemExit(f"Signed data pair is missing: {payload}, {signature}")

    canonical_bytes = TODAY_JSON.read_bytes()
    if ASSET_JSON.read_bytes() != canonical_bytes or dated_json.read_bytes() != canonical_bytes:
        raise SystemExit("Canonical, dated, and embedded JSON differ")
    # Signatures are verified independently below. Do not compare the encoded
    # signature bytes: a regenerated detached signature is not the data
    # contract; the cryptographic verification is the contract.

    for payload, signature in pairs:
        verify(payload, signature)
    print("Detached signatures verified for canonical, dated, and embedded daily data")


if __name__ == "__main__":
    main()
