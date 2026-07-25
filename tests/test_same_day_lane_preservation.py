from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preserve_same_day_language_lanes",
    ROOT / "scripts/preserve_same_day_language_lanes.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def localized(en: str) -> dict[str, str]:
    return {"ar": "", "en": en, "el": ""}


def payload(gospel: str, *, matins: str = "") -> dict:
    readings = [
        {
            "kind": "epistle",
            "reference": localized("Romans"),
            "body": localized("Epistle text"),
        },
        {
            "kind": "gospel",
            "reference": localized("Matthew"),
            "body": localized(gospel),
        },
    ]
    if matins:
        readings.insert(
            0,
            {
                "kind": "matins_gospel",
                "reference": localized("John"),
                "body": localized(matins),
            },
        )
    return {
        "date_iso": "2026-07-25",
        "language": "en",
        "readings": readings,
        "services": [],
    }


class SameDayLanePreservationTests(unittest.TestCase):
    def test_richer_supplement_is_kept(self):
        self.assertEqual(
            [],
            MODULE.regressions(
                payload("Gospel text"),
                payload("Corrected Gospel", matins="Matins text"),
                "en",
            ),
        )

    def test_incomplete_supplement_restores_previous_lane(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_root = root / "candidate"
            published_root = root / "published"
            candidate = candidate_root / "daily/current/en.json"
            published = published_root / "daily/current/en.json"
            candidate.parent.mkdir(parents=True)
            published.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(payload("")), encoding="utf-8")
            published.write_text(json.dumps(payload("Gospel text")), encoding="utf-8")

            state = MODULE.preserve_lane(
                candidate_root,
                published_root,
                "2026-07-25",
                "en",
            )

            self.assertTrue(state.startswith("previous-lane-preserved:"))
            restored = json.loads(candidate.read_text(encoding="utf-8"))
            self.assertEqual(
                "Gospel text",
                restored["readings"][1]["body"]["en"],
            )


if __name__ == "__main__":
    unittest.main()
