package com.orthodoxprayers.privateapp.update;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

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
    public void sameDayCorrectionChecksAreThrottledForThirtyMinutes() {
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(true, 0L, NOW));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, 0L, NOW));
        assertFalse(RefreshPolicy.shouldCheckRemoteOnResume(false, NOW - TimeUnit.MINUTES.toMillis(29), NOW));
        assertTrue(RefreshPolicy.shouldCheckRemoteOnResume(false, NOW - TimeUnit.MINUTES.toMillis(30), NOW));
    }
}
