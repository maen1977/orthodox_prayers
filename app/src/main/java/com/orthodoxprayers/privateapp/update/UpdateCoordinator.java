package com.orthodoxprayers.privateapp.update;

import android.content.Context;

import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
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

/** Single entry point for foreground and persistent local daily refresh scheduling. */
public final class UpdateCoordinator {
    public static final String INPUT_FORCE = "force_local_rebuild";

    private static final String LEGACY_INITIAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-01-refresh";
    private static final String LEGACY_SUPPLEMENTAL_SCHEDULE_WORK =
            "orthodox-trusted-amman-06-refresh";
    private static final String LEGACY_MORNING_SCHEDULE_WORK =
            "orthodox-trusted-amman-0423-refresh-v4";
    private static final String LEGACY_EVENING_SCHEDULE_WORK =
            "orthodox-trusted-amman-1643-refresh-v4";
    private static final String LOCAL_SCHEDULE_WORK =
            "orthodox-local-amman-0003-refresh-v1";
    private static final String LOCAL_DAILY_TAG = "orthodox-local-daily-update";
    private static final String MIDNIGHT_EXECUTION_WORK =
            "orthodox-local-amman-midnight-execution";
    private static final String IMMEDIATE_WORK = "orthodox-local-daily-data-now";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");

    static final int LOCAL_REFRESH_HOUR = 0;
    static final int LOCAL_REFRESH_MINUTE = 3;

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /** Schedules optional network-backed directory verification separately from local daily refresh. */
    public void scheduleChurchDirectoryWeeklySync() {
        ChurchDirectorySchedule.schedule(context);
    }

    /**
     * Schedules one local refresh shortly after the Amman civil date changes.
     * The worker has deliberately no network constraint: it reads only immutable
     * calendar, Scripture and prayer assets already installed with the app.
     */

    public void scheduleDailyRefresh() {
        WorkManager workManager = WorkManager.getInstance(context);
        cancelLegacyRemoteSchedules(workManager);

        long triggerAtMillis = nextAmmanRefreshEpochMillis();
        long delay = Math.max(1_000L, triggerAtMillis - System.currentTimeMillis());
        String datedWorkName = LOCAL_SCHEDULE_WORK + "-"
                + Instant.ofEpochMilli(triggerAtMillis).atZone(AMMAN_ZONE).toLocalDate();
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .addTag(LOCAL_DAILY_TAG)
                .build();
        workManager.enqueueUniqueWork(datedWorkName, ExistingWorkPolicy.KEEP, request);
    }

    private static void cancelLegacyRemoteSchedules(WorkManager workManager) {
        workManager.cancelUniqueWork(LEGACY_INITIAL_SCHEDULE_WORK);
        workManager.cancelUniqueWork(LEGACY_SUPPLEMENTAL_SCHEDULE_WORK);
        workManager.cancelUniqueWork(LEGACY_MORNING_SCHEDULE_WORK);
        workManager.cancelUniqueWork(LEGACY_EVENING_SCHEDULE_WORK);
    }

    /** Backwards-compatible name retained for existing callers and upgrade installs. */
    public void scheduleMidnightRefresh() { scheduleDailyRefresh(); }

    /** Backwards-compatible entry point retained for older callers and tests. */
    public void scheduleDailyAmmanRefreshes() { scheduleDailyRefresh(); }

    /** Backwards-compatible entry point retained for older callers and tests. */
    public void scheduleNextAmmanRefresh() { scheduleDailyRefresh(); }

    /** Legacy method now maps to the one local daily WorkManager schedule. */
    public void schedulePeriodicRefresh() {
        scheduleDailyRefresh();
        scheduleChurchDirectoryWeeklySync();
    }

    /** Compatibility entry point for alarms queued by older installed releases. */
    public void enqueueMidnightRefresh() {
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .addTag(LOCAL_DAILY_TAG)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                MIDNIGHT_EXECUTION_WORK,
                ExistingWorkPolicy.REPLACE,
                request
        );
    }

    public void enqueueImmediateBackgroundRefresh(boolean forceLocalRebuild) {
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, forceLocalRebuild).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .addTag(LOCAL_DAILY_TAG)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                IMMEDIATE_WORK,
                forceLocalRebuild ? ExistingWorkPolicy.REPLACE : ExistingWorkPolicy.KEEP,
                request
        );
    }

    /** Compatibility method name; the app-open check is now entirely local. */
    public boolean shouldCheckRemoteOnResume() { return false; }

    /** Compatibility method name; the app-open check is now entirely local. */
    public boolean shouldCheckRemoteOnAppOpen() { return !repository.isRefreshing(); }

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

    public void refreshForeground(boolean forceLocalRebuild, DataRepository.RefreshCallback callback) {
        repository.refreshAsync(forceLocalRebuild, callback);
    }

    public static long nextAmmanRefreshEpochMillis() {
        return nextAmmanRefreshEpochMillis(LOCAL_REFRESH_HOUR, LOCAL_REFRESH_MINUTE);
    }

    public static long nextAmmanSupplementalRefreshEpochMillis() {
        return nextAmmanRefreshEpochMillis();
    }

    static long nextAmmanRefreshEpochMillis(int hour, int minute) {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime candidate = now.toLocalDate().atTime(hour, minute).atZone(AMMAN_ZONE);
        if (!candidate.isAfter(now)) candidate = candidate.plusDays(1);
        return candidate.toInstant().toEpochMilli();
    }

    public static long nextAmmanMidnightEpochMillis() {
        return nextAmmanRefreshEpochMillis();
    }
}
