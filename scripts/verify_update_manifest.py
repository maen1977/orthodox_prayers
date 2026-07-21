#!/usr/bin/env python3
"""Verify update-manifest signature, metadata, paths, hashes, and payload parity."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "data/update-manifest.json"
SIGNATURE = ROOT / "data/update-manifest.json.sig"
PUBLIC_KEY = ROOT / "canonical/signing/data_signing_public_key.pub"
UPDATE_CONTRACT = ROOT / "canonical/update_contract.json"
SAFE_PATH = re.compile(r"^data/[A-Za-z0-9._/-]+$")


def fail(message: str) -> None:
    raise SystemExit(message)


def checked_path(value: object) -> Path:
    text = str(value or "")
    if not SAFE_PATH.fullmatch(text) or ".." in text.split("/"):
        fail(f"unsafe manifest path: {text!r}")
    path = ROOT / text
    if not path.is_file():
        fail(f"manifest target is missing: {text}")
    return path


def verify_entry(entry: object) -> Path:
    if not isinstance(entry, dict):
        fail("manifest entry is not an object")
    payload_path = checked_path(entry.get("path"))
    signature_path = checked_path(entry.get("signature_path"))
    if signature_path != Path(str(payload_path) + ".sig"):
        fail(f"signature path does not match payload path: {payload_path}")
    data = payload_path.read_bytes()
    if entry.get("sha256") != hashlib.sha256(data).hexdigest():
        fail(f"manifest hash mismatch: {payload_path}")
    if entry.get("size_bytes") != len(data):
        fail(f"manifest size mismatch: {payload_path}")
    return payload_path


def verify_signature() -> None:
    try:
        raw = base64.b64decode(SIGNATURE.read_bytes().strip(), validate=True)
    except Exception as error:
        fail(f"invalid Base64 manifest signature: {error}")
    with tempfile.TemporaryDirectory(prefix="orthodox-manifest-verify-") as directory:
        binary = Path(directory) / "signature.bin"
        binary.write_bytes(raw)
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(PUBLIC_KEY), "-signature", str(binary), str(PAYLOAD)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0 or "Verified OK" not in result.stdout:
            fail("update manifest signature is invalid: " + (result.stdout + result.stderr).strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-date", required=True)
    args = parser.parse_args()
    if not PAYLOAD.is_file() or not SIGNATURE.is_file():
        fail("signed update manifest is missing")
    manifest = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    if manifest.get("manifest_schema_version") != 1:
        fail("unsupported update manifest schema")
    if manifest.get("date_iso") != args.expected_date:
        fail("update manifest date mismatch")
    if not isinstance(manifest.get("revision"), int) or manifest["revision"] < 1:
        fail("invalid update manifest revision")
    minimum_version = manifest.get("minimum_app_version_code")
    if not isinstance(minimum_version, int) or minimum_version < 1:
        fail("invalid minimum app version")
    if not UPDATE_CONTRACT.is_file():
        fail("update contract is missing")
    contract = json.loads(UPDATE_CONTRACT.read_text(encoding="utf-8"))
    if contract.get("manifest_schema_version") != manifest.get("manifest_schema_version"):
        fail("update contract schema differs from manifest")
    if contract.get("minimum_app_version_code") != minimum_version:
        fail("manifest minimum app version differs from update contract")
    verify_signature()
    calendar = verify_entry(manifest.get("calendar"))
    calendar_data = json.loads(calendar.read_text(encoding="utf-8"))
    if calendar_data.get("date_iso") != args.expected_date:
        fail("calendar date differs from manifest date")

    languages = manifest.get("languages")
    if not isinstance(languages, dict) or not languages:
        fail("manifest has no language lanes")
    for language, entry in languages.items():
        if language not in {"ar", "en", "el"}:
            fail(f"unsupported manifest language: {language}")
        dated = verify_entry(entry)
        current = checked_path(entry.get("current_path"))
        current_signature = checked_path(entry.get("current_signature_path"))
        if current_signature != Path(str(current) + ".sig"):
            fail(f"current signature path mismatch: {language}")
        if dated.read_bytes() != current.read_bytes():
            fail(f"manifest dated/current lane mismatch: {language}")
        payload = json.loads(dated.read_text(encoding="utf-8"))
        if payload.get("date_iso") != args.expected_date or payload.get("language") != language:
            fail(f"manifest lane metadata mismatch: {language}")
    print(f"UPDATE_MANIFEST_OK date={args.expected_date} revision={manifest['revision']}")


if __name__ == "__main__":
    main()
