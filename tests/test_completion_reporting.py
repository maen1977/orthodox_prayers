from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CompletionReportingTests(unittest.TestCase):
    def test_service_completion_reports_are_consistent_and_honest(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_completion_reporting.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("technical=45/45", result.stdout)
        self.assertIn("exact=38/45", result.stdout)
        self.assertIn("native_compilations=7/45", result.stdout)
        self.assertIn("ecclesiastical_approval=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
