from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V500ContractTests(unittest.TestCase):
    def test_v500_user_security_and_offline_features_are_wired(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        search = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SearchScreen.java").read_text(encoding="utf-8")
        reminders = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java").read_text(encoding="utf-8")
        store = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DailyDataStore.java").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")

        self.assertIn('android:networkSecurityConfig="@xml/network_security_config"', manifest)
        self.assertIn('.widget.DailyAgendaWidget', manifest)
        self.assertIn('readerBrightnessPercent', preferences)
        self.assertIn('readerTheme', preferences)
        self.assertIn('serviceNote', preferences)
        self.assertIn('quietHoursStartMinute', preferences)
        self.assertIn('recordSearchQuery', search)
        self.assertIn('showNoteDialog', reader)
        self.assertIn('updateReaderProgress', reader)
        self.assertIn('shareCurrentSegment', reader)
        self.assertIn('isWithinQuietHours', reminders)
        self.assertIn('targetScreen', reminders)
        self.assertIn('archive', store)
        self.assertIn('MAX_RETAINED_DAYS_PER_LANGUAGE', store)
        self.assertIn('validateServices(services)', repository)
        self.assertIn('setInstanceFollowRedirects(false)', repository)

        for path in (
            ROOT / "app/src/main/res/xml/network_security_config.xml",
            ROOT / "app/src/main/res/xml/daily_agenda_widget_info.xml",
            ROOT / "app/src/main/res/layout/widget_daily_agenda.xml",
            ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/DataContractTest.java",
            ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/NetworkEndpointSecurityTest.java",
        ):
            self.assertTrue(path.is_file(), path)


if __name__ == "__main__":
    unittest.main()
