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
    public void repeatedStaleChecksAreThrottledForThirtyMinutes() {
        assertFalse(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.MINUTES.toMillis(29), NOW, false, true));
        assertTrue(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.MINUTES.toMillis(30), NOW, false, true));
        assertFalse(RefreshPolicy.shouldRefresh(false, false, true, NOW - TimeUnit.HOURS.toMillis(2), NOW, false, false));
    }

    @Test
    public void appOpenCatchesUpOnlyAfterTheOneAndSixAmmanWindows() {
        long beforeFirst = amman(2026, 7, 25, 0, 30);
        long afterFirst = amman(2026, 7, 25, 1, 5);
        long afterFirstAttempt = amman(2026, 7, 25, 1, 6);
        long beforeSecond = amman(2026, 7, 25, 5, 55);
        long afterSecond = amman(2026, 7, 25, 6, 5);
        long afterSecondAttempt = amman(2026, 7, 25, 6, 6);

        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(true, 0L, afterFirst));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, 0L, beforeFirst));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(
                false, amman(2026, 7, 24, 23, 55), beforeFirst
        ));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, beforeFirst, afterFirst));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(false, afterFirstAttempt, beforeSecond));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, afterFirstAttempt, afterSecond));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(false, afterSecondAttempt, afterSecond));
    }

    private static long amman(int year, int month, int day, int hour, int minute) {
        return ZonedDateTime.of(
                year, month, day, hour, minute, 0, 0, ZoneId.of("Asia/Amman")
        ).toInstant().toEpochMilli();
    }
}
