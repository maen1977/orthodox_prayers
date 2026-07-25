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

    private static final String LEGACY_INITIAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-01-refresh";
    private static final String LEGACY_SUPPLEMENTAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-06-refresh";
    private static final String INITIAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-01-refresh-v2";
    private static final String SUPPLEMENTAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-06-refresh-v2";
    private static final String MIDNIGHT_EXECUTION_WORK =
            "orthodox-trusted-amman-midnight-execution";
    private static final String IMMEDIATE_WORK = "orthodox-trusted-daily-data-now";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
    static final int FIRST_REFRESH_HOUR = 1;
    static final int SECOND_REFRESH_HOUR = 6;
    private static final int REFRESH_MINUTE = 0;

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /**
     * Schedules the two trusted publication windows requested for Amman: 01:00 and 06:00.
     *
     * Content refresh does not require second-level precision, so WorkManager is used instead
     * of exact alarms. Network constraints keep either request pending until connectivity
     * returns. The worker re-establishes both one-time schedules after each completed run.
     */
    public void scheduleDailyRefresh() {
        WorkManager workManager = WorkManager.getInstance(context);
        // Upgrade migration: remove the old stable names. Dated names below keep an
        // already-running 01:00 retry alive when the app opens after that window.
        workManager.cancelUniqueWork(LEGACY_INITIAL_SCHEDULE_WORK);
        workManager.cancelUniqueWork(LEGACY_SUPPLEMENTAL_SCHEDULE_WORK);
        scheduleRefreshWindow(workManager, INITIAL_SCHEDULE_WORK, FIRST_REFRESH_HOUR);
        scheduleRefreshWindow(workManager, SUPPLEMENTAL_SCHEDULE_WORK, SECOND_REFRESH_HOUR);
    }

    private void scheduleRefreshWindow(WorkManager workManager, String workName, int hour) {
        long triggerAtMillis = nextAmmanRefreshEpochMillis(hour, REFRESH_MINUTE);
        long delay = Math.max(1_000L, triggerAtMillis - System.currentTimeMillis());
        String datedWorkName = workName + "-"
                + Instant.ofEpochMilli(triggerAtMillis).atZone(AMMAN_ZONE).toLocalDate();
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        workManager.enqueueUniqueWork(
                datedWorkName,
                ExistingWorkPolicy.KEEP,
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

    /** App-open catch-up is limited to a missed 01:00 or 06:00 Amman window. */
    public boolean shouldCheckRemoteOnResume() {
        return RefreshPolicy.shouldCheckRemoteOnResume(
                repository.isRefreshing(),
                preferences.lastRefreshAttempt(),
                System.currentTimeMillis()
        );
    }

    /** Every new foreground app session performs one lightweight signed-manifest check. */
    public boolean shouldCheckRemoteOnAppOpen() {
        return RefreshPolicy.shouldCheckRemoteOnAppOpen(repository.isRefreshing());
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
        return nextAmmanRefreshEpochMillis(FIRST_REFRESH_HOUR, REFRESH_MINUTE);
    }

    public static long nextAmmanSupplementalRefreshEpochMillis() {
        return nextAmmanRefreshEpochMillis(SECOND_REFRESH_HOUR, REFRESH_MINUTE);
    }

    static long nextAmmanRefreshEpochMillis(int hour, int minute) {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime candidate = now.toLocalDate()
                .atTime(hour, minute)
                .atZone(AMMAN_ZONE);
        if (!candidate.isAfter(now)) candidate = candidate.plusDays(1);
        return candidate.toInstant().toEpochMilli();
    }

    /** Backwards-compatible method name; now returns the next 01:00 Amman refresh instant. */
    public static long nextAmmanMidnightEpochMillis() {
        return nextAmmanRefreshEpochMillis();
    }

    private static Constraints connectedConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
