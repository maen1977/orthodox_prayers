package com.orthodoxprayers.privateapp.work;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import java.time.LocalTime;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.MainActivity;
import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.data.CommemorationDisplayPolicy;
import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.ui.LocalizedResources;


public final class PrayerReminderWorker extends Worker {

    public PrayerReminderWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        if (!(context instanceof OrthodoxPrayersApp)) return Result.failure();
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) context;
        AppPreferences preferences = app.preferences();
        String kind = getInputData().getString(ReminderScheduler.INPUT_KIND);
        if (kind == null || !preferences.remindersEnabled(kind)) return Result.success();

        if (!isWithinQuietHours(preferences)
                && (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)) {
            showNotification(context, app, preferences, kind);
        }
        new ReminderScheduler(context, preferences).schedule(kind);
        return Result.success();
    }

    private static void showNotification(Context context, OrthodoxPrayersApp app, AppPreferences preferences, String kind) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        String channelId = channelId(kind);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    channelId,
                    channelName(context, preferences, kind),
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            channel.setDescription(local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_optional_prayer_and_daily_reading_reminders_f753da85));
            manager.createNotificationChannel(channel);
        }

        Intent intent = new Intent(context, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        intent.putExtra(MainActivity.EXTRA_SCREEN, targetScreen(kind));
        String targetArgument = targetArgument(kind);
        if (targetArgument != null) intent.putExtra(MainActivity.EXTRA_ARGUMENT, targetArgument);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                kind.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        String title;
        String body;
        if (ReminderScheduler.EVENING.equals(kind)) {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_time_for_evening_prayer_81e14848);
            body = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_close_the_day_with_prayer_and_stillness_67ab7213);
        } else if (ReminderScheduler.READING.equals(kind)) {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_today_s_readings_5aad1b50);
            body = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_open_today_s_epistle_and_gospel_980e7457);
        } else if (ReminderScheduler.FEAST.equals(kind)) {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_today_s_commemoration_af76eeaa);
            body = CommemorationDisplayPolicy.displayText(
                    app.repository().today(),
                    app.repository()::localizedValue
            );
            if (body.isEmpty()) return;
        } else if (ReminderScheduler.FAST.equals(kind)) {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_today_s_fasting_aa40c904);
            LocalizedValue fast = app.repository().localizedValue(app.repository().today().optJSONObject("fast"), "");
            if (fast.translationUnavailable || fast.text.trim().isEmpty()) return;
            body = fast.text;
        } else if (ReminderScheduler.PERSONAL.equals(kind)) {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_your_personal_reminder_be9aca0d);
            body = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_take_a_moment_for_prayer_and_stillness_34c3a32d);
        } else {
            title = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_time_for_morning_prayer_717b653a);
            body = local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_begin_your_day_with_prayer_a3c8eb48);
        }

        Notification.Builder notification = new Notification.Builder(context, channelId)
                .setSmallIcon(R.drawable.ic_church_prayers_notification)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(pendingIntent);
        manager.notify(Math.abs(kind.hashCode()), notification.build());
    }

    private static boolean isWithinQuietHours(AppPreferences preferences) {
        int start = preferences.quietHoursStartMinute();
        int end = preferences.quietHoursEndMinute();
        if (start == end) return false;
        LocalTime now = LocalTime.now();
        int minute = now.getHour() * 60 + now.getMinute();
        if (start < end) return minute >= start && minute < end;
        return minute >= start || minute < end;
    }

    private static String channelId(String kind) {
        return "prayer_reminders_" + (kind == null ? "general" : kind.replaceAll("[^a-z0-9_]", ""));
    }

    private static String channelName(Context context, AppPreferences preferences, String kind) {
        if (ReminderScheduler.MORNING.equals(kind)) return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_morning_prayer_a517a36b);
        if (ReminderScheduler.EVENING.equals(kind)) return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_evening_prayer_50c26316);
        if (ReminderScheduler.READING.equals(kind)) return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_daily_readings_295eb6f5);
        if (ReminderScheduler.FEAST.equals(kind)) return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_feasts_and_commemorations_bea321c8);
        if (ReminderScheduler.FAST.equals(kind)) return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_fasting_status_7fa7fda1);
        return local(context, preferences, com.orthodoxprayers.privateapp.R.string.ui_personal_reminders_ac5720b6);
    }

    private static String targetScreen(String kind) {
        if (ReminderScheduler.MORNING.equals(kind) || ReminderScheduler.EVENING.equals(kind)) return "reader";
        if (ReminderScheduler.READING.equals(kind)) return "readings";
        if (ReminderScheduler.PERSONAL.equals(kind)) return "prayers";
        return "home";
    }

    private static String targetArgument(String kind) {
        if (ReminderScheduler.MORNING.equals(kind)) return "morning_prayer";
        if (ReminderScheduler.EVENING.equals(kind)) return "evening_prayer";
        return null;
    }

    private static String local(Context context, AppPreferences preferences, int resourceId) {
        return LocalizedResources.get(context, preferences.effectiveLanguage(), resourceId);
    }
}
