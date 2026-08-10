package com.orthodoxprayers.privateapp.data;

import java.time.LocalTime;

/**
 * Selects the home "Prayer of the Day" by local clock time.
 * This is deliberately deterministic and contains no liturgical text.
 */
public final class PrayerOfDaySelector {
    private PrayerOfDaySelector() {}

    public static String forTime(LocalTime time) {
        if (time == null) return "morning_prayer";
        int minute = time.getHour() * 60 + time.getMinute();
        if (minute >= 4 * 60 && minute < 12 * 60) return "morning_prayer";
        if (minute >= 12 * 60 && minute < 17 * 60 + 30) return "thanksgiving";
        if (minute >= 17 * 60 + 30 && minute < 21 * 60 + 30) return "evening_prayer";
        return "small_compline";
    }
}
