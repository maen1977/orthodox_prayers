package com.orthodoxprayers.privateapp.update;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

import org.junit.Test;

public final class RefreshPolicyTest {
    private static final long NOW = 10_000_000L;

    @Test
    public void neverStartsAnotherRefreshWhileOneIsRunning() {
        assertFalse(RefreshPolicy.shouldRefresh(true, false, false, 0L, NOW, true, true));
    }

    @Test
    public void appOpenAlwaysChecksUnlessAnotherRefreshIsRunning() {
        assertTrue(RefreshPolicy.shouldCheckRemoteOnAppOpen(false));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnAppOpen(true));
    }

    @Test
    public void refreshesOnDayChangeOrFirstStaleCheckOfTheDay() {
        assertTrue(RefreshPolicy.shouldRefresh(false, true, true, NOW, NOW, true, false));
        assertTrue(RefreshPolicy.shouldRefresh(false, false, false, NOW - 1L, NOW, false, true));
    }

    @Test
    public void neverRefreshesCurrentDataAutomatically() {
        assertFalse(RefreshPolicy.shouldRefresh(false, true, false, 0L, NOW, false, false));
        assertFalse(RefreshPolicy.shouldRefresh(false, true, true, NOW - TimeUnit.DAYS.toMillis(2), NOW, false, true));
    }

    @Test
    public void repeatedStaleChecksAreThrottledForFifteenMinutes() {
        assertFalse(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.MINUTES.toMillis(14), NOW, false, true));
        assertTrue(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.MINUTES.toMillis(15), NOW, false, true));
        assertFalse(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.HOURS.toMillis(2), NOW, false, false));
    }

    @Test
    public void appResumeCompatibilityCheckUsesOnlyLocalState() {
        long now = amman(2026, 7, 25, 4, 0);
        long previousAttempt = amman(2026, 7, 24, 23, 55);
        long futureAttempt = amman(2026, 7, 25, 4, 5);

        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(true, 0L, now));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, 0L, now));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, previousAttempt, now));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, now, now));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(false, futureAttempt, now));
    }

    private static long amman(int year, int month, int day, int hour, int minute) {
        return ZonedDateTime.of(
                year, month, day, hour, minute, 0, 0, ZoneId.of("Asia/Amman")
        ).toInstant().toEpochMilli();
    }
}
