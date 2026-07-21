#!/usr/bin/env python3
"""Sign the exact update-manifest bytes with the daily-data signing key."""
from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "data/update-manifest.json"
SIGNATURE = ROOT / "data/update-manifest.json.sig"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-key", required=True, type=Path)
    args = parser.parse_args()
    if not PAYLOAD.is_file():
        raise SystemExit("update manifest is missing")
    if not args.private_key.is_file():
        raise SystemExit("private key was not found")
    if shutil.which("openssl") is None:
        raise SystemExit("OpenSSL is required")

    with tempfile.TemporaryDirectory(prefix="orthodox-manifest-sign-") as directory:
        raw = Path(directory) / "manifest.sig.bin"
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(args.private_key), "-out", str(raw), str(PAYLOAD)],
            cwd=ROOT,
            check=True,
        )
        temporary = SIGNATURE.with_suffix(SIGNATURE.suffix + ".tmp")
        temporary.write_bytes(base64.b64encode(raw.read_bytes()) + b"\n")
        temporary.replace(SIGNATURE)
    print("UPDATE_MANIFEST_SIGNED")


if __name__ == "__main__":
    main()
