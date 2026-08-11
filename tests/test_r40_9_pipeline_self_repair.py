from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE_PATH = ROOT / "scripts" / "update.py"


def load_update_module():
    spec = importlib.util.spec_from_file_location("r40_9_update", UPDATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipelineSelfRepairTests(unittest.TestCase):
    def test_missing_research_module_is_restored_atomically(self) -> None:
        module = load_update_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir(parents=True)
            restored = module.ensure_source_window_research_module(root)
            payload = restored.read_bytes()
            self.assertIn(b"AUTOMATED_FAIL_CLOSED", payload)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), module.SOURCE_WINDOW_RESEARCH_SHA256)
            self.assertTrue(restored.stat().st_mode & 0o100)

    def test_corrupted_research_module_is_replaced(self) -> None:
        module = load_update_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "scripts" / "source_window_research.py"
            target.parent.mkdir(parents=True)
            target.write_text("corrupted", encoding="utf-8")
            restored = module.ensure_source_window_research_module(root)
            self.assertNotEqual(restored.read_text(encoding="utf-8"), "corrupted")
            self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(), module.SOURCE_WINDOW_RESEARCH_SHA256)

    def test_current_workflow_is_local_and_legacy_repair_cli_remains_available(self) -> None:
        build = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/keep_required_workflows.py", build)
        self.assertIn("python scripts/run_local_daily_release_gate.py", build)
        self.assertFalse((ROOT / ".github/workflows/build.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/update.yml").exists())

    def test_update_cli_exposes_repair_only_mode(self) -> None:
        text = UPDATE_PATH.read_text(encoding="utf-8")
        self.assertIn('"--repair-pipeline-only"', text)
        self.assertIn("PIPELINE_REPAIR_ONLY_OK", text)
        self.assertIn("PIPELINE_SELF_REPAIR_OK", text)


if __name__ == "__main__":
    unittest.main()
