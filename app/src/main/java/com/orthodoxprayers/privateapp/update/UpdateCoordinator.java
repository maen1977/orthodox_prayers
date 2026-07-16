package com.orthodoxprayers.privateapp.update;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.work.DailyUpdateWorker;

import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

/** Single entry point for foreground and persistent automatic refresh scheduling. */
public final class UpdateCoordinator {
    public static final String INPUT_FORCE = "force_full_download";
    private static final String PERIODIC_WORK = "orthodox-trusted-daily-data-fallback";
    private static final String MIDNIGHT_WORK = "orthodox-trusted-amman-midnight";
    private static final String QUARTER_PAST_WORK = "orthodox-trusted-amman-quarter-past";
    private static final String IMMEDIATE_WORK = "orthodox-trusted-daily-data-now";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
    private static final int MIDNIGHT_HOUR = 0;
    private static final int MIDNIGHT_MINUTE = 0;
    private static final int CONFIRMATION_HOUR = 0;
    private static final int CONFIRMATION_MINUTE = 15;

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /**
     * Persistent safety net. WorkManager is deliberately used instead of exact alarms:
     * Android may defer background work, while the two daily one-time requests and the
     * foreground check together guarantee eventual refresh without restricted permissions.
     */
    public void schedulePeriodicRefresh() {
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                DailyUpdateWorker.class,
                12,
                TimeUnit.HOURS,
                1,
                TimeUnit.HOURS
        )
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_WORK,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
        );
    }

    /** Schedule both requested Amman checks: midnight and the 00:15 confirmation. */
    public void scheduleDailyAmmanRefreshes() {
        scheduleOneDailyWork(MIDNIGHT_WORK, MIDNIGHT_HOUR, MIDNIGHT_MINUTE, false);
        // The confirmation run deliberately bypasses the "already current" shortcut so
        // a corrected server snapshot published just after midnight is still accepted.
        scheduleOneDailyWork(QUARTER_PAST_WORK, CONFIRMATION_HOUR, CONFIRMATION_MINUTE, true);
    }

    /** Backwards-compatible entry point used by older callers/tests. */
    public void scheduleNextAmmanRefresh() {
        scheduleDailyAmmanRefreshes();
    }

    private void scheduleOneDailyWork(String uniqueName, int hour, int minute, boolean forceFullDownload) {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime nextRun = now.withHour(hour).withMinute(minute).withSecond(0).withNano(0);
        if (!nextRun.isAfter(now)) nextRun = nextRun.plusDays(1);
        long delay = Math.max(1_000L, Duration.between(now, nextRun).toMillis());

        Data input = new Data.Builder().putBoolean(INPUT_FORCE, forceFullDownload).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                uniqueName,
                ExistingWorkPolicy.REPLACE,
                request
        );
    }

    public void enqueueImmediateBackgroundRefresh(boolean forceFullDownload) {
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, forceFullDownload).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                IMMEDIATE_WORK,
                forceFullDownload ? ExistingWorkPolicy.REPLACE : ExistingWorkPolicy.KEEP,
                request
        );
    }

    /** Every return to the foreground performs a lightweight endpoint-scoped ETag check. */
    public boolean shouldCheckRemoteOnResume() {
        return !repository.isRefreshing();
    }

    public boolean shouldRefresh(boolean dayChanged, boolean resumed) {
        long lastAttempt = preferences.lastRefreshAttempt();
        boolean attemptedToday = lastAttempt > 0L
                && repository.currentAmmanDate().equals(
                        Instant.ofEpochMilli(lastAttempt).atZone(AMMAN_ZONE).toLocalDate().toString()
                );
        return RefreshPolicy.shouldRefresh(
                repository.isRefreshing(),
                repository.hasUsableCurrentData(),
                attemptedToday,
                lastAttempt,
                System.currentTimeMillis(),
                dayChanged,
                resumed
        );
    }

    public void refreshForeground(boolean forceFullDownload, DataRepository.RefreshCallback callback) {
        repository.refreshAsync(forceFullDownload, callback);
    }

    private static Constraints connectedConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
