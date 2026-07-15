#!/usr/bin/env python3
"""Verify every published independent language lane that is available for a date."""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "canonical/signing/data_signing_public_key.pub"
LANGUAGES = ("ar", "el", "en")


def verify_signature(payload: Path, signature: Path) -> None:
    if not signature.is_file():
        raise SystemExit(f"missing lane signature: {signature}")
    raw = base64.b64decode(signature.read_bytes().strip(), validate=True)
    with tempfile.TemporaryDirectory() as directory:
        binary_signature = Path(directory) / "signature.bin"
        binary_signature.write_bytes(raw)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(PUBLIC_KEY),
                "-signature",
                str(binary_signature),
                str(payload),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise SystemExit(f"lane signature invalid: {payload}: {result.stderr.strip()}")


def verify_lane(path: Path, expected_date: str, language: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing lane: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("date_iso") != expected_date or data.get("language") != language:
        raise SystemExit(f"lane metadata invalid: {path}")
    if data.get("schema_version") != 9 or data.get("lane_schema_version") != 2:
        raise SystemExit(f"lane schema invalid: {path}")
    if data.get("machine_translation_used") is not False:
        raise SystemExit(f"translation flag invalid: {path}")
    if data.get("automatic_diacritization_used") is not False:
        raise SystemExit(f"diacritization flag invalid: {path}")
    if not isinstance(data.get("services"), list) or not data["services"]:
        raise SystemExit(f"lane services missing: {path}")
    if not isinstance(data.get("readings"), list):
        raise SystemExit(f"lane readings missing: {path}")
    verify_signature(path, Path(str(path) + ".sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--language", choices=LANGUAGES)
    args = parser.parse_args()

    if args.language:
        languages = [args.language]
    else:
        current = ROOT / "data/daily/current"
        languages = [language for language in LANGUAGES if (current / f"{language}.json").is_file()]
        if not languages:
            raise SystemExit("no current language lane was published")

    for language in languages:
        dated = ROOT / f"data/daily/{args.date}/{language}.json"
        current = ROOT / f"data/daily/current/{language}.json"
        verify_lane(dated, args.date, language)
        verify_lane(current, args.date, language)
        if dated.read_bytes() != current.read_bytes():
            raise SystemExit(f"dated/current lane mismatch: {language}")

    print("LANGUAGE_LANES_OK " + ",".join(languages))


if __name__ == "__main__":
    main()
