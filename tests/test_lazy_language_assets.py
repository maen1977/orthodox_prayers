from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"


class LazyLanguageAssetTests(unittest.TestCase):
    def test_repository_constructor_does_not_parse_all_language_assets(self):
        source = SOURCE.read_text(encoding="utf-8")
        constructor = source[source.index("private DataRepository(") : source.index("private void indexCalendarDays")]
        self.assertNotIn('loadJsonAsset("data/native/library_ar.json")', constructor)
        self.assertNotIn('loadJsonAsset("data/native/library_en.json")', constructor)
        self.assertNotIn('loadJsonAsset("data/native/library_el.json")', constructor)
        self.assertNotIn('loadJsonAsset("data/search/search_index_ar.json")', constructor)
        self.assertNotIn('loadJsonAsset("data/search/search_index_en.json")', constructor)
        self.assertNotIn('loadJsonAsset("data/search/search_index_el.json")', constructor)

    def test_only_selected_library_and_on_demand_search_index_are_loaded(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"data/native/library_" + normalized + ".json"', source)
        self.assertIn('"data/search/search_index_" + normalized + ".json"', source)
        self.assertRegex(source, re.compile(r"ensureLanguageAssets\(preferences\.effectiveLanguage\(\), true\)"))
        self.assertIn("activeLanguageSearchIndex = null;", source)

    def test_language_change_clears_the_heavy_asset_cache(self):
        source = SOURCE.read_text(encoding="utf-8")
        reload_block = source[source.index("public synchronized void reloadForSelectedLanguage") : source.index("public java.util.List<String> availableCachedDates")]
        self.assertIn("clearLanguageAssetCache();", reload_block)


if __name__ == "__main__":
    unittest.main()
