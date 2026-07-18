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
import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;


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
                    channelName(preferences, kind),
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            channel.setDescription(local(preferences, "تذكيرات اختيارية للصلاة وقراءات اليوم", "Optional prayer and daily-reading reminders", "Προαιρετικὲς ὑπενθυμίσεις"));
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
            title = local(preferences, "حان وقت صلاة المساء", "Time for evening prayer", "Ὥρα γιὰ ἑσπερινὴ προσευχή");
            body = local(preferences, "اختم يومك بالصلاة والهدوء.", "Close the day with prayer and stillness.", "Κλείσε τὴν ἡμέρα μὲ προσευχή.");
        } else if (ReminderScheduler.READING.equals(kind)) {
            title = local(preferences, "قراءات اليوم", "Today’s readings", "Τὰ σημερινὰ ἀναγνώσματα");
            body = local(preferences, "افتح رسالة وإنجيل اليوم.", "Open today’s Epistle and Gospel.", "Ἄνοιξε τὸν Ἀπόστολο καὶ τὸ Εὐαγγέλιο.");
        } else if (ReminderScheduler.FEAST.equals(kind)) {
            title = local(preferences, "تذكار اليوم", "Today’s commemoration", "Ἡ σημερινὴ μνήμη");
            LocalizedValue feast = app.repository().localizedValue(app.repository().today().optJSONObject("feast"), "");
            if (feast.translationUnavailable || feast.text.trim().isEmpty()) return;
            body = feast.text;
        } else if (ReminderScheduler.FAST.equals(kind)) {
            title = local(preferences, "صيام اليوم", "Today’s fasting", "Ἡ σημερινὴ νηστεία");
            LocalizedValue fast = app.repository().localizedValue(app.repository().today().optJSONObject("fast"), "");
            if (fast.translationUnavailable || fast.text.trim().isEmpty()) return;
            body = fast.text;
        } else if (ReminderScheduler.PERSONAL.equals(kind)) {
            title = local(preferences, "تذكيرك الشخصي", "Your personal reminder", "Προσωπικὴ ὑπενθύμιση");
            body = local(preferences, "خذ دقيقة للصلاة والهدوء.", "Take a moment for prayer and stillness.", "Πάρε λίγο χρόνο γιὰ προσευχή.");
        } else {
            title = local(preferences, "حان وقت صلاة الصباح", "Time for morning prayer", "Ὥρα γιὰ πρωινὴ προσευχή");
            body = local(preferences, "ابدأ يومك بالصلاة.", "Begin your day with prayer.", "Ἄρχισε τὴν ἡμέρα μὲ προσευχή.");
        }

        Notification.Builder notification = new Notification.Builder(context, channelId)
                .setSmallIcon(R.drawable.ic_nav_prayers)
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

    private static String channelName(AppPreferences preferences, String kind) {
        if (ReminderScheduler.MORNING.equals(kind)) return local(preferences, "صلاة الصباح", "Morning prayer", "Πρωινὴ προσευχή");
        if (ReminderScheduler.EVENING.equals(kind)) return local(preferences, "صلاة المساء", "Evening prayer", "Ἑσπερινὴ προσευχή");
        if (ReminderScheduler.READING.equals(kind)) return local(preferences, "قراءات اليوم", "Daily readings", "Ἡμερήσια ἀναγνώσματα");
        if (ReminderScheduler.FEAST.equals(kind)) return local(preferences, "الأعياد والتذكارات", "Feasts and commemorations", "Ἑορτὲς καὶ μνῆμες");
        if (ReminderScheduler.FAST.equals(kind)) return local(preferences, "حالة الصيام", "Fasting status", "Κατάσταση νηστείας");
        return local(preferences, "تذكيرات شخصية", "Personal reminders", "Προσωπικὲς ὑπενθυμίσεις");
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

    private static String local(AppPreferences preferences, String ar, String en, String el) {
        if ("en".equals(preferences.effectiveLanguage())) return en;
        if ("el".equals(preferences.effectiveLanguage())) return el;
        return ar;
    }
}
