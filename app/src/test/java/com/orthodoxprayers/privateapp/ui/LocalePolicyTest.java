package com.orthodoxprayers.privateapp.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.time.ZoneId;

public final class LocalePolicyTest {
    @Test
    public void selectedLanguageControlsDateFormattingInsteadOfDeviceLocale() {
        long timestamp = 1_768_478_400_000L;
        String arabic = LocalePolicy.formatTimestamp(timestamp, "ar", ZoneId.of("Asia/Amman"));
        String english = LocalePolicy.formatTimestamp(timestamp, "en", ZoneId.of("Asia/Amman"));
        String greek = LocalePolicy.formatTimestamp(timestamp, "el", ZoneId.of("Asia/Amman"));

        assertTrue(UiKit.containsArabic(arabic));
        assertFalse(UiKit.containsArabic(english));
        assertTrue(greek.codePoints().anyMatch(codePoint -> Character.UnicodeScript.of(codePoint) == Character.UnicodeScript.GREEK));
    }

    @Test
    public void technicalIdentifiersAreDirectionallyIsolated() {
        assertEquals("\u2066signed_remote\u2069", LocalePolicy.isolateTechnical("signed_remote"));
        assertEquals("—", LocalePolicy.isolateTechnical(" "));
    }

    @Test
    public void clockValuesAreClamped() {
        assertEquals("00:00", LocalePolicy.formatClock(-5, "en"));
        assertEquals("23:59", LocalePolicy.formatClock(2000, "en"));
    }
}
