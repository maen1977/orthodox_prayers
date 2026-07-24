from __future__ import annotations

import hashlib
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/create_clean_source_archive.py"


class CleanSourceArchiveTests(unittest.TestCase):
    def test_archive_is_deterministic_clean_and_preserves_gradlew_mode(self):
        gradlew = ROOT / "gradlew"
        original_mode = stat.S_IMODE(gradlew.stat().st_mode)
        try:
            # Reproduce Windows/GitHub web uploads, where gradlew commonly lands
            # as 0644. The clean archive must still record it as executable.
            gradlew.chmod(original_mode & ~0o111)
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                first = directory / "source-one.zip"
                second = directory / "source-two.zip"
                for output in (first, second):
                    subprocess.run(
                        [sys.executable, str(SCRIPT), str(output)],
                        cwd=ROOT,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    checksum = output.with_suffix(output.suffix + ".sha256")
                    self.assertTrue(checksum.is_file())
                    self.assertTrue(checksum.read_text(encoding="utf-8").startswith(hashlib.sha256(output.read_bytes()).hexdigest()))

                self.assertEqual(first.read_bytes(), second.read_bytes())

                with zipfile.ZipFile(first) as archive:
                    infos = archive.infolist()
                    names = [info.filename for info in infos]
                    self.assertEqual(len(names), len(set(names)))
                    self.assertIn("orthodox_prayers/gradlew", names)
                    for name in names:
                        path = PurePosixPath(name)
                        self.assertNotIn(".git", path.parts)
                        self.assertNotIn("__pycache__", path.parts)
                        self.assertNotIn(".pytest_cache", path.parts)
                        self.assertFalse(path.name.startswith("COMMIT_MESSAGE"))
                        self.assertFalse(path.name.lower().endswith((".pem", ".key", ".keystore", ".jks", ".pyc")))

                    gradlew_info = archive.getinfo("orthodox_prayers/gradlew")
                    mode = (gradlew_info.external_attr >> 16) & 0xFFFF
                    self.assertTrue(mode & stat.S_IXUSR)
        finally:
            gradlew.chmod(original_mode)

    def test_root_layout_overwrites_repository_paths_without_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "full-root.zip"
            subprocess.run(
                [sys.executable, str(SCRIPT), str(output), "--root-layout"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("app/build.gradle.kts", names)
                self.assertIn("scripts/verify_r19_patch.py", names)
                self.assertNotIn("orthodox_prayers/app/build.gradle.kts", names)
                build = archive.read("app/build.gradle.kts").decode("utf-8")
                self.assertIn('versionName = "5.0.16"', build)
                self.assertIn("versionCode = 50016", build)


if __name__ == "__main__":
    unittest.main()
