from __future__ import annotations

import binascii
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_play_store_assets.py"
spec = importlib.util.spec_from_file_location("validate_play_store_assets", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


class PlayStoreAssetTests(unittest.TestCase):
    def test_committed_store_artwork_is_complete_and_exact_size(self):
        self.assertEqual(module.read_png(ROOT / "play-store/assets/app-icon-512.png")[:2], (512, 512))
        self.assertEqual(module.read_png(ROOT / "play-store/assets/feature-graphic-1024x500.png")[:2], (1024, 500))

    def test_truncated_png_is_rejected_even_when_header_is_present(self):
        raw = (
            module.PNG_SIGNATURE
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", b"not-real-image-data")
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.png"
            path.write_bytes(raw)
            with self.assertRaisesRegex(module.PngError, "missing IEND"):
                module.read_png(path)

    def test_png_crc_corruption_is_rejected(self):
        path = ROOT / "play-store/assets/app-icon-512.png"
        raw = bytearray(path.read_bytes())
        raw[-5] ^= 0x01
        with tempfile.TemporaryDirectory() as tmp:
            corrupted = Path(tmp) / "corrupted.png"
            corrupted.write_bytes(raw)
            with self.assertRaises(module.PngError):
                module.read_png(corrupted)


if __name__ == "__main__":
    unittest.main()
