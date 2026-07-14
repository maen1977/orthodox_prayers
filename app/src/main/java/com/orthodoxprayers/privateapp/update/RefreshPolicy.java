package com.orthodoxprayers.privateapp.update;

import java.util.concurrent.TimeUnit;

/** Pure decision logic for once-per-day refresh behavior and stale-data retry throttling. */
public final class RefreshPolicy {
    static final long STALE_RETRY_INTERVAL_MS = TimeUnit.MINUTES.toMillis(30);

    private RefreshPolicy() {}

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
        // The midnight watcher and WorkManager already cover background/day-change refreshes.
        if (!resumed) return false;
        long age = Math.max(0L, now - lastAttempt);
        return age >= STALE_RETRY_INTERVAL_MS;
    }
}
