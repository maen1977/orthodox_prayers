package com.orthodoxprayers.privateapp.reminder;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.work.PrayerReminderWorker;

import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

/** Schedules opt-in daily reminders without exact-alarm permissions. */
public final class ReminderScheduler {
    public static final String MORNING = "morning";
    public static final String EVENING = "evening";
    public static final String READING = "reading";
    public static final String FEAST = "feast";
    public static final String FAST = "fast";
    public static final String PERSONAL = "personal";
    public static final String INPUT_KIND = "reminder_kind";
    public static final int NOTIFICATION_PERMISSION_REQUEST = 4102;

    private final Context context;
    private final AppPreferences preferences;

    public ReminderScheduler(Context context, AppPreferences preferences) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
    }

    public void scheduleAll() {
        schedule(MORNING, 6 * 60 + 30);
        schedule(READING, 8 * 60);
        schedule(EVENING, 21 * 60);
        schedule(FEAST, 7 * 60);
        schedule(FAST, 7 * 60 + 15);
        schedule(PERSONAL, 18 * 60);
    }

    public void schedule(String kind) {
        schedule(kind, defaultMinute(kind));
    }

    public void cancel(String kind) {
        WorkManager.getInstance(context).cancelUniqueWork(uniqueName(kind));
    }

    private void schedule(String kind, int fallbackMinute) {
        if (!preferences.remindersEnabled(kind)) {
            cancel(kind);
            return;
        }
        int minuteOfDay = preferences.reminderMinuteOfDay(kind, fallbackMinute);
        ZonedDateTime now = ZonedDateTime.now(ZoneId.systemDefault());
        ZonedDateTime next = now.withHour(minuteOfDay / 60).withMinute(minuteOfDay % 60).withSecond(0).withNano(0);
        if (!next.isAfter(now)) next = next.plusDays(1);
        long delay = Math.max(1_000L, Duration.between(now, next).toMillis());

        Data input = new Data.Builder().putString(INPUT_KIND, kind).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(PrayerReminderWorker.class)
                .setInputData(input)
                .setInitialDelay(delay, TimeUnit.MILLISECONDS)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(uniqueName(kind), ExistingWorkPolicy.REPLACE, request);
    }

    private static int defaultMinute(String kind) {
        if (EVENING.equals(kind)) return 21 * 60;
        if (READING.equals(kind)) return 8 * 60;
        if (FEAST.equals(kind)) return 7 * 60;
        if (FAST.equals(kind)) return 7 * 60 + 15;
        if (PERSONAL.equals(kind)) return 18 * 60;
        return 6 * 60 + 30;
    }

    private static String uniqueName(String kind) {
        return "orthodox-prayer-reminder-" + kind;
    }
}
