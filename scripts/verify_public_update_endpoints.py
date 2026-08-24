#!/usr/bin/env python3
"""Verify that the freshly published signed update is reachable over public HTTPS."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "canonical/signing/data_signing_public_key.pub"
PRIMARY_ROOT = "https://raw.githubusercontent.com/maen1977/orthodox_prayers/verified-data"
MIRROR_ROOT = "https://cdn.jsdelivr.net/gh/maen1977/orthodox_prayers@verified-data"
USER_AGENT = "OrthodoxPrayers-PublicationVerifier/5.6.5"
MAX_PUBLIC_PAYLOAD_BYTES = 12_000_000
SAFE_PUBLIC_PATH = re.compile(r"^data/[A-Za-z0-9._/-]+$")


def fetch(url: str, *, max_bytes: int, token: str) -> bytes:
    separator = "&" if "?" in url else "?"
    request = urllib.request.Request(
        f"{url}{separator}verify={token}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache, no-store, max-age=0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"http_{response.status}:{url}")
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise RuntimeError(f"response_too_large:{url}")
    return payload


def verify_signature(payload: bytes, encoded_signature: bytes) -> None:
    raw = base64.b64decode(encoded_signature.strip(), validate=True)
    with tempfile.TemporaryDirectory(prefix="orthodox-public-endpoint-") as directory:
        directory_path = Path(directory)
        payload_path = directory_path / "payload"
        signature_path = directory_path / "signature.bin"
        payload_path.write_bytes(payload)
        signature_path.write_bytes(raw)
        result = subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-verify", str(PUBLIC_KEY),
                "-signature", str(signature_path), str(payload_path),
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or "Verified OK" not in result.stdout:
            raise RuntimeError("public_signature_invalid")


def safe_public_path(value: object, *, language: str, field: str) -> str:
    path = str(value or "")
    if not SAFE_PUBLIC_PATH.fullmatch(path) or ".." in path.split("/"):
        raise RuntimeError(f"public_manifest_unsafe_path:{language}:{field}")
    return path


def declared_payload_size(language: str, entry: object) -> int:
    if not isinstance(entry, dict):
        raise RuntimeError(f"public_manifest_entry_invalid:{language}")
    size = entry.get("size_bytes")
    if type(size) is not int or size < 1 or size > MAX_PUBLIC_PAYLOAD_BYTES:
        raise RuntimeError(f"public_declared_size_invalid:{language}:{size}")
    return size


def verify_root(root: str, expected_date: str, token: str, *, verify_payloads: bool) -> None:
    manifest_url = f"{root}/data/update-manifest.json"
    manifest_bytes = fetch(manifest_url, max_bytes=64_000, token=token)
    signature_bytes = fetch(manifest_url + ".sig", max_bytes=16_384, token=token)
    verify_signature(manifest_bytes, signature_bytes)
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("date_iso") != expected_date:
        raise RuntimeError(
            f"public_manifest_date_mismatch:{manifest.get('date_iso')}:{expected_date}"
        )
    if not verify_payloads:
        return
    languages = manifest.get("languages")
    if not isinstance(languages, dict) or not languages:
        raise RuntimeError("public_manifest_languages_invalid")
    for language, entry in languages.items():
        if language not in {"ar", "en", "el"}:
            raise RuntimeError(f"public_manifest_language_unsupported:{language}")
        declared_size = declared_payload_size(language, entry)
        path = safe_public_path(entry.get("path"), language=language, field="path")
        signature_path = safe_public_path(
            entry.get("signature_path"), language=language, field="signature_path"
        )
        if signature_path != path + ".sig":
            raise RuntimeError(f"public_signature_path_mismatch:{language}")
        payload = fetch(f"{root}/{path}", max_bytes=declared_size, token=token)
        if len(payload) != declared_size:
            raise RuntimeError(f"public_size_mismatch:{language}")
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            raise RuntimeError(f"public_hash_mismatch:{language}")
        payload_signature = fetch(
            f"{root}/{signature_path}",
            max_bytes=16_384,
            token=token,
        )
        verify_signature(payload, payload_signature)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay-seconds", type=int, default=10)
    args = parser.parse_args()
    if args.attempts < 1 or args.delay_seconds < 0:
        raise SystemExit("invalid retry configuration")

    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        token = f"{int(time.time())}-{attempt}"
        try:
            verify_root(PRIMARY_ROOT, args.expected_date, token, verify_payloads=True)
            print(f"PUBLIC_UPDATE_PRIMARY_OK date={args.expected_date} attempt={attempt}")
            break
        except Exception as error:
            last_error = error
            print(f"PUBLIC_UPDATE_PRIMARY_RETRY attempt={attempt} error={error}", flush=True)
            if attempt < args.attempts:
                time.sleep(args.delay_seconds)
    else:
        raise SystemExit(f"public primary endpoint verification failed: {last_error}")

    # The mirror is a resilience path and may have a short CDN propagation delay.
    # Report its state without blocking the authoritative primary publication.
    try:
        verify_root(MIRROR_ROOT, args.expected_date, f"mirror-{int(time.time())}", verify_payloads=False)
        print(f"PUBLIC_UPDATE_MIRROR_OK date={args.expected_date}")
    except Exception as error:
        print(f"PUBLIC_UPDATE_MIRROR_PENDING date={args.expected_date} error={error}")


if __name__ == "__main__":
    main()
