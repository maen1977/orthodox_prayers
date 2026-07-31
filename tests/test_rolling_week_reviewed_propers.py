from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_update_module():
    path = ROOT / "scripts/update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("rolling_week_update_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RollingWeekReviewedPropersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_update_module()
        cls.patterns = (
            re.compile(r"تذكار اليوم بحسب التقويم الكنسي القديم", re.I),
            re.compile(
                r"(?:Today[’']s|Daily) commemoration according to the old "
                r"(?:church|ecclesiastical) calendar",
                re.I,
            ),
            re.compile(
                r"(?:Ἡ σημερινὴ μνήμη|Μνήμη τῆς ἡμέρας) κατὰ τὸ παλαιὸ "
                r"ἐκκλησιαστικὸ ἡμερολόγιο",
                re.I,
            ),
        )

    def strings(self, value):
        if isinstance(value, dict):
            for child in value.values():
                yield from self.strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from self.strings(child)
        elif isinstance(value, str):
            yield value

    def test_unreviewed_weekday_is_explicitly_unavailable(self):
        info = self.update.day_info(date(2026, 7, 29))
        self.assertEqual("UNAVAILABLE_PENDING_ECCLESIASTICAL_REVIEW", info["feast_status"])
        self.assertEqual(
            "تعذّر التحقق من تذكار هذا اليوم من المصدر الرسمي المحلي؛ تظهر آخر معلومة موثقة إن توفرت",
            info["feast_ar"],
        )

    def test_pinned_sunday_name_is_used(self):
        info = self.update.day_info(date(2026, 8, 2))
        self.assertEqual("PINNED_REVIEWED_ANNUAL_ENTRY", info["feast_status"])
        self.assertEqual("الأحد 9 بعد العنصرة", info["feast_ar"])
        self.assertEqual("9 Sunday after Pentecost", info["feast_en"])

    def test_today_plus_seven_contains_no_unreviewed_generic_proper(self):
        start = date(2026, 7, 29)
        for offset in range(8):
            payload = self.update.build_day(start + timedelta(days=offset))
            for text in self.strings(payload):
                self.assertFalse(
                    any(pattern.search(text) for pattern in self.patterns),
                    msg=f"unreviewed proper leaked for offset {offset}: {text[:120]}",
                )


if __name__ == "__main__":
    unittest.main()
