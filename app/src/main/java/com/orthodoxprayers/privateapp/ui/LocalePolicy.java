package com.orthodoxprayers.privateapp.ui;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.FormatStyle;
import java.util.Locale;

/** Keeps app-owned dates, times, and technical identifiers stable in the selected UI language. */
public final class LocalePolicy {
    private static final char LEFT_TO_RIGHT_ISOLATE = '\u2066';
    private static final char POP_DIRECTIONAL_ISOLATE = '\u2069';

    private LocalePolicy() {}

    public static Locale localeForLanguage(String language) {
        if ("ar".equals(language)) return Locale.forLanguageTag("ar-JO");
        if ("el".equals(language)) return Locale.forLanguageTag("el-GR");
        return Locale.ENGLISH;
    }

    public static String formatTimestamp(long timestamp, String language, ZoneId zone) {
        DateTimeFormatter formatter = DateTimeFormatter
                .ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT)
                .withLocale(localeForLanguage(language))
                .withZone(zone == null ? ZoneId.systemDefault() : zone);
        return formatter.format(Instant.ofEpochMilli(timestamp));
    }

    public static String formatClock(int minuteOfDay, String language) {
        int safe = Math.max(0, Math.min(1439, minuteOfDay));
        return String.format(localeForLanguage(language), "%02d:%02d", safe / 60, safe % 60);
    }

    /** Prevents hashes and machine identifiers from reordering surrounding Arabic text. */
    public static String isolateTechnical(String value) {
        if (value == null || value.trim().isEmpty()) return "—";
        return LEFT_TO_RIGHT_ISOLATE + value.trim() + POP_DIRECTIONAL_ISOLATE;
    }
}
