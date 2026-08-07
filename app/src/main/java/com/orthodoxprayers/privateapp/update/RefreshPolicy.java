package com.orthodoxprayers.privateapp.update;

import java.util.concurrent.TimeUnit;

/** Pure decision logic for local daily refresh behavior. */
public final class RefreshPolicy {
    static final long STALE_RETRY_INTERVAL_MS = TimeUnit.MINUTES.toMillis(15);

    private RefreshPolicy() {}

    /** Compatibility name retained; the operation is a local asset check. */
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
        if (!resumed) return false;
        long age = Math.max(0L, now - lastAttempt);
        return age >= STALE_RETRY_INTERVAL_MS;
    }

    /** Compatibility name retained; no publication window or network is consulted. */
    public static boolean shouldCheckRemoteOnResume(boolean refreshing, long lastAttempt, long now) {
        return !refreshing && (lastAttempt <= 0L || lastAttempt <= now);
    }
}
