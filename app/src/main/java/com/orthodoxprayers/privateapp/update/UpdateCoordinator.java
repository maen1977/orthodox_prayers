package com.orthodoxprayers.privateapp.update;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

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
    public static final String ACTION_MIDNIGHT_UPDATE =
            "com.orthodoxprayers.privateapp.action.MIDNIGHT_UPDATE";

    private static final String MIDNIGHT_FALLBACK_WORK =
            "orthodox-trusted-amman-midnight-fallback";
    private static final String MIDNIGHT_EXECUTION_WORK =
            "orthodox-trusted-amman-midnight-execution";
    private static final String IMMEDIATE_WORK = "orthodox-trusted-daily-data-now";
    private static final int MIDNIGHT_ALARM_REQUEST_CODE = 1200;
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");

    private final Context context;
    private final AppPreferences preferences;
    private final DataRepository repository;

    public UpdateCoordinator(Context context, AppPreferences preferences, DataRepository repository) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.repository = repository;
    }

    /**
     * Schedules the next daily refresh for exactly 00:00 in Amman.
     *
     * On Android versions that grant exact-alarm access, AlarmManager wakes the app at
     * midnight and an expedited WorkManager task performs the verified network refresh.
     * If exact alarms are unavailable, a one-time WorkManager request is aligned to the
     * same midnight and remains the safe platform-compliant fallback.
     */
    public void scheduleMidnightRefresh() {
        long triggerAtMillis = nextAmmanMidnightEpochMillis();
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        PendingIntent alarmIntent = midnightAlarmIntent(context);

        if (alarmManager != null && canScheduleExactAlarm(alarmManager)) {
            alarmManager.cancel(alarmIntent);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        triggerAtMillis,
                        alarmIntent
                );
            } else {
                alarmManager.setExact(AlarmManager.RTC_WAKEUP, triggerAtMillis, alarmIntent);
            }
            WorkManager.getInstance(context).cancelUniqueWork(MIDNIGHT_FALLBACK_WORK);
            return;
        }

        scheduleWorkManagerMidnightFallback(triggerAtMillis);
    }

    /** Backwards-compatible entry point retained for older callers and upgrade installs. */
    public void scheduleDailyAmmanRefreshes() {
        scheduleMidnightRefresh();
    }

    /** Backwards-compatible entry point retained for older callers and tests. */
    public void scheduleNextAmmanRefresh() {
        scheduleMidnightRefresh();
    }

    /** Legacy method now maps to the single 00:00 schedule; no 12-hour updates are created. */
    public void schedulePeriodicRefresh() {
        scheduleMidnightRefresh();
    }

    /** Called by the midnight alarm receiver. The worker is expedited whenever quota permits. */
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

    public static boolean isExactMidnightEnabled(Context context) {
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        return alarmManager != null && canScheduleExactAlarm(alarmManager);
    }

    public static Intent exactAlarmSettingsIntent(Context context) {
        Intent intent = new Intent("android.settings.REQUEST_SCHEDULE_EXACT_ALARM");
        intent.setData(android.net.Uri.parse("package:" + context.getPackageName()));
        return intent;
    }

    public static long nextAmmanMidnightEpochMillis() {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime nextMidnight = now.toLocalDate().plusDays(1).atStartOfDay(AMMAN_ZONE);
        return nextMidnight.toInstant().toEpochMilli();
    }

    private void scheduleWorkManagerMidnightFallback(long triggerAtMillis) {
        long delay = Math.max(1_000L, triggerAtMillis - System.currentTimeMillis());
        Data input = new Data.Builder().putBoolean(INPUT_FORCE, true).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(DailyUpdateWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setConstraints(connectedConstraints())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                MIDNIGHT_FALLBACK_WORK,
                ExistingWorkPolicy.REPLACE,
                request
        );
    }

    private static boolean canScheduleExactAlarm(AlarmManager alarmManager) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarmManager.canScheduleExactAlarms();
    }

    private static PendingIntent midnightAlarmIntent(Context context) {
        Intent intent = new Intent(context, MidnightUpdateReceiver.class)
                .setAction(ACTION_MIDNIGHT_UPDATE);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getBroadcast(context, MIDNIGHT_ALARM_REQUEST_CODE, intent, flags);
    }

    private static Constraints connectedConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
