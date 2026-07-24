#!/usr/bin/env python3
"""Build one Android-compatible independent native-language daily lane."""
from __future__ import annotations

import argparse
import base64
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
    """Return a structurally complete payload containing one language only.

    A lane is not independent merely because it has its own URL and signature.
    Localized strings from the other two languages and their per-language source
    evidence must also be absent from its signed envelope.
    """
    if language not in LANGS:
        raise ValueError(f"unsupported language: {language}")
    if isinstance(value, list):
        return [keep_only_language(item, language) for item in value]
    if not isinstance(value, dict):
        return value

    language_keys = LANGS.intersection(value)
    if language_keys:
        slots = [value.get(key) for key in language_keys]
        is_localized_text = all(
            slot is None or isinstance(slot, (str, int, float, bool))
            for slot in slots
        )
        result = {
            key: keep_only_language(child, language)
            for key, child in value.items()
            if key not in LANGS
        }
        if is_localized_text:
            for candidate in sorted(LANGS):
                result[candidate] = value.get(candidate, "") if candidate == language else ""
        elif language in value:
            result[language] = keep_only_language(value[language], language)
        return result

    return {key: keep_only_language(child, language) for key, child in value.items()}


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
