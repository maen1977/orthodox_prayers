package com.orthodoxprayers.privateapp.update;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

/** Pure decision logic for daily refresh behavior and safe network throttling. */
public final class RefreshPolicy {
    static final long STALE_RETRY_INTERVAL_MS = TimeUnit.MINUTES.toMillis(15);
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");

    private RefreshPolicy() {}

    /** A fresh foreground session always checks the small signed manifest first. */
    public static boolean shouldCheckRemoteOnAppOpen(boolean refreshing) {
        return !refreshing;
    }

    public static boolean shouldRefresh(
            boolean refreshing,
            boolean current,
            boolean attemptedToday,
            long lastAttempt,
            long now,
            boolean dayChanged,
            boolean resumed
    ) {
        if (refreshing) return false;
        if (dayChanged) return true;
        if (current) return false;
        if (!attemptedToday || lastAttempt == 0L) return true;
        // Repeated stale-data retries are only useful when the user returns to the app.
        // WorkManager already covers background/day-change refreshes.
        if (!resumed) return false;
        long age = Math.max(0L, now - lastAttempt);
        return age >= STALE_RETRY_INTERVAL_MS;
    }

    public static boolean shouldCheckRemoteOnResume(
            boolean refreshing,
            long lastAttempt,
            long now
    ) {
        if (refreshing) return false;
        if (lastAttempt <= 0L) return true;
        if (lastAttempt > now) return false;

        ZonedDateTime ammanNow = Instant.ofEpochMilli(now).atZone(AMMAN_ZONE);
        LocalDate today = ammanNow.toLocalDate();
        ZonedDateTime publicationWindow = today
                .atTime(UpdateCoordinator.DAILY_REFRESH_HOUR, UpdateCoordinator.REFRESH_MINUTE)
                .atZone(AMMAN_ZONE);
        Instant attemptedAt = Instant.ofEpochMilli(lastAttempt);

        if (ammanNow.isBefore(publicationWindow)) return false;
        return attemptedAt.isBefore(publicationWindow.toInstant());
    }
}
