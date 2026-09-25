from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LiturgyRoutingContractTests(unittest.TestCase):
    def test_calendar_contains_explicit_service_types_through_2050(self):
        counts = {"chrysostom": 0, "basil": 0, "presanctified": 0}
        for path in sorted((ROOT / "app/src/main/assets/data/calendar").glob("calendar_*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for day in payload.get("days", []):
                service_type = (day.get("liturgy_service_selection") or {}).get("service_type")
                if service_type in counts:
                    counts[service_type] += 1
        self.assertGreater(counts["chrysostom"], 0)
        self.assertGreater(counts["basil"], 0)
        self.assertGreater(counts["presanctified"], 0)

    def test_reader_does_not_auto_compose_adjacent_offices(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        method = source[source.index("private static boolean isFollowAlongLiturgy"):source.index("/**", source.index("private static boolean isFollowAlongLiturgy"))]
        self.assertIn('service.optBoolean("follow_along", false)', method)
        self.assertIn('service.optBoolean("follow_along_requested", false)', method)
        self.assertNotIn('"divine_liturgy".equals(id)', method)

    def test_calendar_routes_basil_and_presanctified_to_their_own_ids(self):
        for name in ("CalendarDayScreen.java", "UpcomingScreen.java"):
            source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens" / name).read_text(encoding="utf-8")
            self.assertIn('"divine_liturgy_basil"', source)
            self.assertIn('"presanctified_liturgy"', source)


if __name__ == "__main__":
    unittest.main()
