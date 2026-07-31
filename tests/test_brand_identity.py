from __future__ import annotations

import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


class BrandIdentityTests(unittest.TestCase):
    def test_launcher_name_is_fixed_as_church_prayers(self) -> None:
        base = ET.parse(RES / "values/strings.xml").getroot()
        app_name = next(item for item in base.findall("string") if item.attrib.get("name") == "app_name")
        self.assertEqual("Church Prayers", app_name.text)
        self.assertEqual("false", app_name.attrib.get("translatable"))
        for localized in (RES / "values-en/strings.xml", RES / "values-el/strings.xml"):
            names = {item.attrib.get("name") for item in ET.parse(localized).getroot().findall("string")}
            self.assertNotIn("app_name", names)

    def test_supplied_jerusalem_cross_is_the_launcher_and_store_icon(self) -> None:
        foreground = (RES / "drawable/ic_launcher_foreground.xml").read_text(encoding="utf-8")
        self.assertIn("@drawable/church_prayers_cross", foreground)
        self.assertNotIn("orthodox_cross_icon", foreground)
        launcher = ROOT / "app/src/main/res/drawable-nodpi/church_prayers_cross.png"
        store = ROOT / "play-store/assets/app-icon-512.png"
        self.assertEqual((1024, 1024), png_size(launcher))
        self.assertEqual((512, 512), png_size(store))
        self.assertGreater(launcher.stat().st_size, 100_000)
        self.assertGreater(store.stat().st_size, 10_000)

    def test_jerusalem_cross_is_used_for_monochrome_and_notifications(self) -> None:
        mono = (RES / "drawable/ic_launcher_monochrome.xml").read_text(encoding="utf-8")
        notification = (RES / "drawable/ic_church_prayers_notification.xml").read_text(encoding="utf-8")
        worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java").read_text(encoding="utf-8")
        for text in (mono, notification):
            self.assertIn("M10.25,2h3.5v20h-3.5z", text)
            self.assertIn("M5.75,3.75h1.5v4.5h-1.5z", text)
        self.assertIn("R.drawable.ic_church_prayers_notification", worker)

    def test_downloadable_files_use_church_prayers_name(self) -> None:
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("release/Church-Prayers-$APP_VERSION-debug.apk", workflow)
        self.assertIn("release/Church-Prayers-$RELEASE_VERSION.apk", workflow)
        self.assertIn("release/Church-Prayers-$RELEASE_VERSION.aab", workflow)
        upload_block = workflow.split("- name: Upload Church Prayers debug APK and reports", 1)[1].split("  release:", 1)[0]
        self.assertNotIn("app/build/outputs/apk/debug/app-debug.apk", upload_block)
        self.assertTrue((ROOT / "release/branding/Church-Prayers.ico").is_file())
        self.assertTrue((ROOT / "release/branding/Church-Prayers-icon-512.png").is_file())

    def test_android_identity_is_preserved_for_in_place_updates(self) -> None:
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        settings = (ROOT / "settings.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('applicationId = "com.orthodoxprayers.privateapp"', build)
        self.assertIn('rootProject.name = "ChurchPrayers"', settings)


if __name__ == "__main__":
    unittest.main()
