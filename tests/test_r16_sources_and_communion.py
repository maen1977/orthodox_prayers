import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class R16SourcesAndCommunionTests(unittest.TestCase):
    def setUp(self):
        self.library = json.loads((ROOT / "data/services/library.json").read_text(encoding="utf-8"))
        self.services = {x["id"]: x for x in self.library["services"]}

    def test_source_registry_is_packaged_and_visible(self):
        registry = json.loads((ROOT / "app/src/main/assets/data/source_registry.json").read_text(encoding="utf-8"))
        ids = {x["id"] for x in registry["sources"]}
        self.assertIn("orthodox_jordan", ids)
        self.assertIn("ebible_arabic_van_dyck", ids)
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertIn('host.navigate("sources", null)', settings)

    def test_liturgy_does_not_claim_unproven_completeness(self):
        service = self.services["divine_liturgy"]
        self.assertEqual("القداس الإلهي", service["title"]["ar"])
        self.assertFalse(service["source_provenance"]["complete_service_claim"])
        self.assertFalse(any(x.get("type") == "quiet_prayer" for x in service["segments"]))

    def test_communion_prayers_are_separate_and_source_linked(self):
        liturgy = self.services["divine_liturgy"]
        related = {x["service_id"] for x in liturgy["related_services"]}
        self.assertIn("pre_communion_prayers", related)
        self.assertIn("thanksgiving_after_communion", related)
        for sid in ("pre_communion_prayers", "thanksgiving_after_communion"):
            service = self.services[sid]
            self.assertEqual("communion", service["category"])
            self.assertEqual("orthodox_jordan", service["source_provenance"]["source_id"])
            self.assertFalse(service["source_provenance"]["complete_text"])

    def test_daily_variables_remain_separate_from_personal_preparation(self):
        pre = self.services["pre_communion_prayers"]
        notice = pre["notice"]["ar"]
        self.assertIn("ليست خدمة السَحَر", notice)
        self.assertIn("الأحد المتغيرة", notice)

if __name__ == "__main__":
    unittest.main()
