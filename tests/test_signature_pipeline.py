from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required")
class SignaturePipelineTests(unittest.TestCase):
    def setUp(self):
        self.payload = ROOT / "data/calendar/today.json"
        self.signature = ROOT / "data/calendar/today.json.sig"
        self.public_key = ROOT / "canonical/signing/data_signing_public_key.pub"

    def verify(self, payload: Path, signature: Path) -> bool:
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "signature.bin"
            raw.write_bytes(base64.b64decode(signature.read_bytes().strip(), validate=True))
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(self.public_key), "-signature", str(raw), str(payload)],
                text=True,
                capture_output=True,
            )
            return result.returncode == 0 and "Verified OK" in result.stdout

    def test_committed_signature_is_valid(self):
        self.assertTrue(self.verify(self.payload, self.signature))

    def test_single_byte_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            tampered = Path(temp) / "today.json"
            content = bytearray(self.payload.read_bytes())
            content[len(content) // 2] ^= 1
            tampered.write_bytes(content)
            self.assertFalse(self.verify(tampered, self.signature))

    def test_android_der_key_matches_committed_pem_key(self):
        result = subprocess.run(
            ["openssl", "pkey", "-pubin", "-in", str(self.public_key), "-outform", "DER"],
            capture_output=True,
            check=True,
        )
        android_key = ROOT / "app/src/main/res/raw/data_signing_public_key.der"
        self.assertEqual(result.stdout, android_key.read_bytes())


if __name__ == "__main__":
    unittest.main()
