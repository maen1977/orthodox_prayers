#!/usr/bin/env python3
"""Validate Google Play artwork before a release is allowed.

The validator intentionally uses only the Python standard library so it runs in
both local source archives and CI before Android/Gradle dependencies are set up.
It verifies the complete PNG chunk stream (including CRCs and IEND), exact store
sizes, and optional real screenshot requirements.
"""
from __future__ import annotations

import argparse
import binascii
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "play-store" / "assets"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngError(ValueError):
    pass


def read_png(path: Path) -> tuple[int, int, int]:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise PngError("invalid PNG signature")

    offset = len(PNG_SIGNATURE)
    width = height = 0
    idat_bytes = 0
    saw_ihdr = False
    saw_iend = False

    while offset < len(raw):
        if offset + 12 > len(raw):
            raise PngError("truncated chunk header")
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        chunk_type = raw[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(raw):
            raise PngError(f"truncated {chunk_type.decode('ascii', 'replace')} chunk")
        payload = raw[data_start:data_end]
        expected_crc = struct.unpack(">I", raw[data_end:crc_end])[0]
        actual_crc = binascii.crc32(chunk_type)
        actual_crc = binascii.crc32(payload, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise PngError(f"CRC mismatch in {chunk_type.decode('ascii', 'replace')} chunk")

        if chunk_type == b"IHDR":
            if saw_ihdr or length != 13:
                raise PngError("invalid IHDR")
            width, height = struct.unpack(">II", payload[:8])
            saw_ihdr = True
        elif chunk_type == b"IDAT":
            idat_bytes += length
        elif chunk_type == b"IEND":
            if length != 0:
                raise PngError("invalid IEND")
            saw_iend = True
            offset = crc_end
            break
        offset = crc_end

    if not saw_ihdr:
        raise PngError("missing IHDR")
    if idat_bytes <= 0:
        raise PngError("missing image data")
    if not saw_iend:
        raise PngError("missing IEND")
    if offset != len(raw):
        raise PngError("unexpected bytes after IEND")
    return width, height, len(raw)


def validate_png(path: Path, expected_size: tuple[int, int], minimum_bytes: int) -> str:
    if not path.is_file():
        raise SystemExit(f"Missing Play asset: {path.relative_to(ROOT)}")
    try:
        width, height, byte_count = read_png(path)
    except (OSError, PngError) as exc:
        raise SystemExit(f"Invalid Play asset {path.relative_to(ROOT)}: {exc}") from exc
    if (width, height) != expected_size:
        raise SystemExit(
            f"Invalid Play asset size {path.relative_to(ROOT)}: "
            f"{width}x{height}; expected {expected_size[0]}x{expected_size[1]}"
        )
    if byte_count < minimum_bytes:
        raise SystemExit(
            f"Play asset looks unexpectedly empty {path.relative_to(ROOT)}: {byte_count} bytes"
        )
    return f"{path.relative_to(ROOT)}={width}x{height}/{byte_count}B"


def screenshot_paths() -> list[Path]:
    root = ASSETS / "screenshots"
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.png") if path.is_file())


def validate_screenshots() -> list[str]:
    paths = screenshot_paths()
    # Two phone screenshots per locale is the minimum useful release set.
    by_locale: dict[str, list[Path]] = {"ar": [], "en": [], "el": []}
    for path in paths:
        locale = path.parent.name.lower()
        if locale in by_locale:
            by_locale[locale].append(path)

    missing = [locale for locale, items in by_locale.items() if len(items) < 2]
    if missing:
        raise SystemExit(
            "Play screenshots are incomplete. Add at least two real phone screenshots under "
            "play-store/assets/screenshots/{ar,en,el}/. Missing: " + ", ".join(missing)
        )

    results: list[str] = []
    for locale, items in by_locale.items():
        for path in items:
            try:
                width, height, byte_count = read_png(path)
            except (OSError, PngError) as exc:
                raise SystemExit(f"Invalid screenshot {path.relative_to(ROOT)}: {exc}") from exc
            if width < 320 or height < 320 or max(width, height) / min(width, height) > 2.2:
                raise SystemExit(
                    f"Screenshot dimensions are outside the supported phone range: "
                    f"{path.relative_to(ROOT)}={width}x{height}"
                )
            results.append(f"{locale}:{path.name}={width}x{height}/{byte_count}B")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-screenshots",
        action="store_true",
        help="Block a store release unless real Arabic, English, and Greek screenshots are present.",
    )
    args = parser.parse_args()

    results = [
        validate_png(ASSETS / "app-icon-512.png", (512, 512), 10_000),
        validate_png(ASSETS / "feature-graphic-1024x500.png", (1024, 500), 20_000),
    ]
    if args.require_screenshots:
        results.extend(validate_screenshots())

    print("PLAY_STORE_ASSETS_OK " + " ".join(results))


if __name__ == "__main__":
    main()
