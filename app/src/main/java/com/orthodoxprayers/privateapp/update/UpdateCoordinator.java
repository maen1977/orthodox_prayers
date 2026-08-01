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
    private static final String MORNING_SCHEDULE_WORK =
            "orthodox-trusted-amman-0423-refresh-v4";
    private static final String EVENING_SCHEDULE_WORK =
            "orthodox-trusted-amman-1643-refresh-v4";
    private static final String MIDNIGHT_EXECUTION_WORK =
            "orthodox-trusted-amman-midnight-execution";
    private static final String IMMEDIATE_WORK = "orthodox-trusted-daily-data-now";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
    static final int MORNING_REFRESH_HOUR = 4;
    static final int MORNING_REFRESH_MINUTE = 23;
    static final int EVENING_REFRESH_HOUR = 16;
    static final int EVENING_REFRESH_MINUTE = 43;

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /**
     * Schedules two trusted daily refreshes at 04:23 and 16:43 Asia/Amman.
     *
     * GitHub Actions publishes signed content twice every 24 hours. WorkManager
     * performs best-effort device checks after both publication times, while every
     * fresh app foreground session still performs a lightweight signed-manifest check.
     */
    public void scheduleDailyRefresh() {
        WorkManager workManager = WorkManager.getInstance(context);
        // Cancel all historical two-window work names during upgrade migration.
        workManager.cancelUniqueWork(LEGACY_INITIAL_SCHEDULE_WORK);
        workManager.cancelUniqueWork(LEGACY_SUPPLEMENTAL_SCHEDULE_WORK);
        scheduleRefreshWindow(workManager, MORNING_SCHEDULE_WORK, MORNING_REFRESH_HOUR, MORNING_REFRESH_MINUTE);
        scheduleRefreshWindow(workManager, EVENING_SCHEDULE_WORK, EVENING_REFRESH_HOUR, EVENING_REFRESH_MINUTE);
    }

    private void scheduleRefreshWindow(WorkManager workManager, String workName, int hour, int minute) {
        long triggerAtMillis = nextAmmanRefreshEpochMillis(hour, minute);
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
        workManager.enqueueUniqueWork(datedWorkName, ExistingWorkPolicy.KEEP, request);
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

    /** App-open catch-up checks for the latest signed 04:23 or 16:43 Amman publication. */
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
        return nextAmmanRefreshEpochMillis(MORNING_REFRESH_HOUR, MORNING_REFRESH_MINUTE);
    }

    public static long nextAmmanSupplementalRefreshEpochMillis() {
        return nextAmmanRefreshEpochMillis(EVENING_REFRESH_HOUR, EVENING_REFRESH_MINUTE);
    }

    static long nextAmmanRefreshEpochMillis(int hour, int minute) {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime candidate = now.toLocalDate()
                .atTime(hour, minute)
                .atZone(AMMAN_ZONE);
        if (!candidate.isAfter(now)) candidate = candidate.plusDays(1);
        return candidate.toInstant().toEpochMilli();
    }

    /** Backwards-compatible method name; now returns the next 04:23 Amman refresh instant. */
    public static long nextAmmanMidnightEpochMillis() {
        return nextAmmanRefreshEpochMillis();
    }

    private static Constraints connectedConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
