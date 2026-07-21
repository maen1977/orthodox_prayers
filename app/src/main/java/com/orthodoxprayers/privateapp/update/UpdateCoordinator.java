package com.orthodoxprayers.privateapp.update;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.OutOfQuotaPolicy;
import androidx.work.WorkManager;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.work.DailyUpdateWorker;

import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

/** Single entry point for foreground and persistent automatic refresh scheduling. */
public final class UpdateCoordinator {
    public static final String INPUT_FORCE = "force_full_download";

    private static final String DAILY_SCHEDULE_WORK =
            "orthodox-trusted-amman-daily-refresh";
    private static final String MIDNIGHT_EXECUTION_WORK =
            "orthodox-trusted-amman-midnight-execution";
    private static final String IMMEDIATE_WORK = "orthodox-trusted-daily-data-now";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
    private static final int DAILY_REFRESH_HOUR = 0;
    private static final int DAILY_REFRESH_MINUTE = 5;

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /**
     * Schedules one persistent, network-aware refresh shortly after the Amman date changes.
     *
     * Content refresh does not require second-level precision, so WorkManager is used instead
     * of exact alarms. The five-minute publication grace period avoids racing the server at
     * 00:00 while still refreshing before normal morning use. Network constraints keep the
     * request pending until connectivity returns, and the worker schedules the following day.
     */
    public void scheduleDailyRefresh() {
        long triggerAtMillis = nextAmmanRefreshEpochMillis();
        long delay = Math.max(1_000L, triggerAtMillis - System.currentTimeMillis());
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                DAILY_SCHEDULE_WORK,
                ExistingWorkPolicy.REPLACE,
                request
        );
    }

    /** Backwards-compatible name retained for existing callers and upgrade installs. */
    public void scheduleMidnightRefresh() {
        scheduleDailyRefresh();
    }

    /** Backwards-compatible entry point retained for older callers and tests. */
    public void scheduleDailyAmmanRefreshes() {
        scheduleDailyRefresh();
    }

    /** Backwards-compatible entry point retained for older callers and tests. */
    public void scheduleNextAmmanRefresh() {
        scheduleDailyRefresh();
    }

    /** Legacy method now maps to the single daily WorkManager schedule. */
    public void schedulePeriodicRefresh() {
        scheduleDailyRefresh();
    }

    /** Compatibility entry point for upgrades that may still deliver an old midnight intent. */
    public void enqueueMidnightRefresh() {
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setConstraints(connectedConstraints())
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                MIDNIGHT_EXECUTION_WORK,
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

    /** Same-day correction checks are throttled instead of running on every foreground return. */
    public boolean shouldCheckRemoteOnResume() {
        return RefreshPolicy.shouldCheckRemoteOnResume(
                repository.isRefreshing(),
                preferences.lastRefreshAttempt(),
                System.currentTimeMillis()
        );
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

    public static long nextAmmanRefreshEpochMillis() {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime candidate = now.toLocalDate()
                .atTime(DAILY_REFRESH_HOUR, DAILY_REFRESH_MINUTE)
                .atZone(AMMAN_ZONE);
        if (!candidate.isAfter(now)) candidate = candidate.plusDays(1);
        return candidate.toInstant().toEpochMilli();
    }

    /** Backwards-compatible method name; now returns the 00:05 Amman refresh instant. */
    public static long nextAmmanMidnightEpochMillis() {
        return nextAmmanRefreshEpochMillis();
    }

    private static Constraints connectedConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
