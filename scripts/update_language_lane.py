#!/usr/bin/env python3
"""Build one Android-compatible independent native-language daily lane."""
from __future__ import annotations

import argparse
import base64
import copy
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"ar", "el", "en"}


def sign(path: Path, key: Path) -> Path:
    signature = path.with_suffix(path.suffix + ".sig")
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "signature.bin"
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(key), "-out", str(raw), str(path)],
            check=True,
        )
        signature.write_bytes(base64.b64encode(raw.read_bytes()) + b"\n")
    return signature


def keep_only_language(value: Any, language: str) -> Any:
    """Copy the complete verified schema into a separately signed language lane.

    The Android client itself enforces the selected language and never displays another
    lane as a translation. Keeping the other verified fields in the envelope preserves
    structural fallbacks such as fasting metadata while each endpoint, ETag and signature
    remains independent.
    """
    if language not in LANGS:
        raise ValueError(f"unsupported language: {language}")
    return copy.deepcopy(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, choices=sorted(LANGS))
    parser.add_argument("--date", required=True)
    signing = parser.add_mutually_exclusive_group(required=True)
    signing.add_argument("--private-key", type=Path)
    signing.add_argument(
        "--unsigned",
        action="store_true",
        help="Write validated lane JSON only and remove any stale detached signatures.",
    )
    parser.add_argument("--source", default="data/calendar/today.json")
    args = parser.parse_args()

    if args.private_key is not None and not args.private_key.is_file():
        raise SystemExit(f"private key was not found: {args.private_key}")

    source = ROOT / args.source
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("date_iso") != args.date:
        raise SystemExit(f"source date {data.get('date_iso')!r} does not match requested date {args.date!r}")
    language = args.language
    lane = keep_only_language(data, language)
    lane.update(
        {
            "lane_schema_version": 2,
            "language": language,
            "date_iso": args.date,
            "calendar_authority": "jerusalem_patriarchate",
            "calendar": "julian_old_calendar",
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
            "language_source_policy": (data.get("language_sources") or {}).get(language, {}),
        }
    )

    dated = ROOT / f"data/daily/{args.date}/{language}.json"
    dated.parent.mkdir(parents=True, exist_ok=True)
    dated.write_text(json.dumps(lane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    current = ROOT / f"data/daily/current/{language}.json"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_bytes(dated.read_bytes())

    if args.unsigned:
        Path(str(dated) + ".sig").unlink(missing_ok=True)
        Path(str(current) + ".sig").unlink(missing_ok=True)
        status = "LANE_UPDATE_UNSIGNED_OK"
    else:
        sign(dated, args.private_key)
        sign(current, args.private_key)
        status = "LANE_UPDATE_OK"

    print(
        f"{status} language={language} date={args.date} "
        f"services={len(lane.get('services', []))} readings={len(lane.get('readings', []))}"
    )


if __name__ == "__main__":
    main()
