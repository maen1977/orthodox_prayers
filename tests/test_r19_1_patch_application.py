from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class R191PatchApplicationTests(unittest.TestCase):
    def test_quality_gate_rejects_partial_r19_before_unit_tests(self):
        gate = (ROOT / "scripts/run_quality_gate.py").read_text(encoding="utf-8")
        verifier = (ROOT / "scripts/verify_r19_patch.py").read_text(encoding="utf-8")
        self.assertLess(
            gate.index('"scripts/verify_r19_patch.py"'),
            gate.index('"-m", "unittest"'),
        )
        self.assertIn("PATCH_R19_PARTIAL_OR_MISPLACED", verifier)
        self.assertIn("repository root", verifier)

    def test_root_patch_has_no_wrapper_and_contains_release_build_file(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "r19-root-patch.zip"
            subprocess.run(
                [sys.executable, "scripts/create_r19_root_patch.py", str(archive)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertIn("app/build.gradle.kts", names)
                self.assertIn("scripts/verify_r19_patch.py", names)
                self.assertIn("tests/test_r19_refinement.py", names)
                self.assertFalse(any(name.startswith("orthodox_prayers/") for name in names))
                build = bundle.read("app/build.gradle.kts").decode("utf-8")
                self.assertIn('versionName = "5.0.16"', build)
                self.assertIn("versionCode = 50016", build)


if __name__ == "__main__":
    unittest.main()
