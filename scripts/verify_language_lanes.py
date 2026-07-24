#!/usr/bin/env python3
"""Validate every available independent language lane for a date."""
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


def isolation_error(value: object, language: str, pointer: str = "") -> str:
    """Return the first foreign language slot retained in a signed lane."""
    if isinstance(value, list):
        for index, child in enumerate(value):
            error = isolation_error(child, language, f"{pointer}[{index}]")
            if error:
                return error
        return ""
    if not isinstance(value, dict):
        return ""

    present = set(value).intersection(LANGUAGES)
    if present:
        scalar_slots = all(
            value.get(key) is None or isinstance(value.get(key), (str, int, float, bool))
            for key in present
        )
        if scalar_slots:
            for other in LANGUAGES:
                if other != language and str(value.get(other) or "").strip():
                    return f"{pointer}.{other}: foreign localized text"
        else:
            for other in LANGUAGES:
                if other != language and other in value:
                    return f"{pointer}.{other}: foreign language evidence"

    for key, child in value.items():
        error = isolation_error(child, language, f"{pointer}.{key}" if pointer else key)
        if error:
            return error
    return ""


def verify_signature(payload: Path, signature: Path) -> None:
    if not signature.is_file():
        raise SystemExit(f"missing lane signature: {signature}")
    try:
        raw = base64.b64decode(signature.read_bytes().strip(), validate=True)
    except Exception as error:
        raise SystemExit(f"invalid Base64 lane signature: {signature}: {error}") from error
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
            detail = (result.stdout + result.stderr).strip()
            raise SystemExit(f"lane signature invalid: {payload}: {detail}")


def verify_lane(
    path: Path,
    expected_date: str,
    language: str,
    unsigned: bool,
    allow_legacy_multilingual: bool = False,
) -> None:
    if not path.is_file():
        raise SystemExit(f"missing lane: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(f"invalid lane JSON: {path}: {error}") from error
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
    leak = isolation_error(data, language)
    if leak and not allow_legacy_multilingual:
        raise SystemExit(f"language lane is not isolated: {path}: {leak}")
    if leak:
        print(f"LEGACY_MULTILINGUAL_LANE_ACCEPTED path={path} detail={leak}")

    signature = Path(str(path) + ".sig")
    if unsigned:
        if signature.exists():
            raise SystemExit(f"stale signature exists beside unsigned lane: {signature}")
    else:
        verify_signature(path, signature)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument(
        "--allow-legacy-multilingual",
        action="store_true",
        help="Migration-only: accept already-signed R19 envelopes until Update republishes isolated R20 lanes.",
    )
    parser.add_argument(
        "--unsigned",
        action="store_true",
        help="Validate JSON structure and require detached signatures to be absent.",
    )
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
        verify_lane(
            dated,
            args.date,
            language,
            args.unsigned,
            args.allow_legacy_multilingual,
        )
        verify_lane(
            current,
            args.date,
            language,
            args.unsigned,
            args.allow_legacy_multilingual,
        )
        if dated.read_bytes() != current.read_bytes():
            raise SystemExit(f"dated/current lane mismatch: {language}")

    status = "LANGUAGE_LANES_UNSIGNED_OK" if args.unsigned else "LANGUAGE_LANES_OK"
    print(status + " " + ",".join(languages))


if __name__ == "__main__":
    main()
