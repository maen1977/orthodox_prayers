from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_public_update_endpoints.py"
SPEC = importlib.util.spec_from_file_location("verify_public_update_endpoints", SCRIPT)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class PublicEndpointPayloadLimitTests(unittest.TestCase):
    def test_signed_manifest_size_above_legacy_six_megabyte_limit_is_used(self):
        payload = b"x" * 6_000_001
        manifest = {
            "date_iso": "2026-07-31",
            "languages": {
                "ar": {
                    "path": "data/daily/2026-07-31/ar.json",
                    "signature_path": "data/daily/2026-07-31/ar.json.sig",
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            },
        }
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        requested_limits: dict[str, int] = {}

        def fake_fetch(url: str, *, max_bytes: int, token: str) -> bytes:
            del token
            requested_limits[url] = max_bytes
            if url.endswith("data/update-manifest.json"):
                return manifest_bytes
            if url.endswith("data/update-manifest.json.sig"):
                return b"manifest-signature"
            if url.endswith("data/daily/2026-07-31/ar.json"):
                return payload
            if url.endswith("data/daily/2026-07-31/ar.json.sig"):
                return b"payload-signature"
            raise AssertionError(url)

        with mock.patch.object(verifier, "fetch", side_effect=fake_fetch), mock.patch.object(
            verifier, "verify_signature"
        ):
            verifier.verify_root(
                "https://updates.example.test", "2026-07-31", "token", verify_payloads=True
            )

        self.assertEqual(
            len(payload),
            requested_limits[
                "https://updates.example.test/data/daily/2026-07-31/ar.json"
            ],
        )

    def test_declared_payload_size_uses_same_twelve_megabyte_ceiling_as_android(self):
        self.assertEqual(
            12_000_000,
            verifier.declared_payload_size("ar", {"size_bytes": 12_000_000}),
        )
        for invalid in (0, -1, 12_000_001, True, "7000000", None):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                verifier.declared_payload_size("ar", {"size_bytes": invalid})

    def test_public_paths_remain_fail_closed(self):
        self.assertEqual(
            "data/daily/2026-07-31/ar.json",
            verifier.safe_public_path(
                "data/daily/2026-07-31/ar.json", language="ar", field="path"
            ),
        )
        for invalid in ("../secret", "data/../secret", "https://evil.test/payload"):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                verifier.safe_public_path(invalid, language="ar", field="path")


if __name__ == "__main__":
    unittest.main()
