#!/usr/bin/env python3
"""Re-sign the exact language-lane bytes that are about to be published."""
from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "canonical/signing/data_signing_public_key.pub"
LANGUAGES = ("ar", "el", "en")


def sign_and_verify(payload: Path, private_key: Path) -> None:
    signature = Path(str(payload) + ".sig")
    with tempfile.TemporaryDirectory(prefix="orthodox-lane-sign-") as directory:
        raw = Path(directory) / "signature.bin"
        subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(private_key),
                "-out",
                str(raw),
                str(payload),
            ],
            cwd=ROOT,
            check=True,
        )
        encoded = base64.b64encode(raw.read_bytes()) + b"\n"
        temporary = signature.with_suffix(signature.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(signature)

        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(PUBLIC_KEY),
                "-signature",
                str(raw),
                str(payload),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or "Verified OK" not in result.stdout:
            detail = (result.stdout + result.stderr).strip()
            raise SystemExit(f"fresh lane signature verification failed for {payload}: {detail}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--language", choices=LANGUAGES)
    args = parser.parse_args()

    if shutil.which("openssl") is None:
        raise SystemExit("OpenSSL is required")
    if not args.private_key.is_file():
        raise SystemExit(f"private key was not found: {args.private_key}")
    if not PUBLIC_KEY.is_file():
        raise SystemExit(f"public key was not found: {PUBLIC_KEY}")

    selected = (args.language,) if args.language else LANGUAGES
    signed: list[str] = []
    for language in selected:
        dated = ROOT / f"data/daily/{args.date}/{language}.json"
        current = ROOT / f"data/daily/current/{language}.json"
        present = (dated.is_file(), current.is_file())
        if present == (False, False) and args.language is None:
            continue
        if present != (True, True):
            raise SystemExit(f"incomplete language lane for {language}: dated={present[0]} current={present[1]}")
        if dated.read_bytes() != current.read_bytes():
            raise SystemExit(f"dated/current lane mismatch before signing: {language}")
        sign_and_verify(dated, args.private_key)
        sign_and_verify(current, args.private_key)
        signed.append(language)

    if not signed:
        raise SystemExit("no language lanes were available to sign")
    print("LANGUAGE_LANES_RESIGNED " + ",".join(signed))


if __name__ == "__main__":
    main()
