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
    private static final String CHANNEL_ID = "prayer_reminders";

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

        if (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
            showNotification(context, app, preferences, kind);
        }
        new ReminderScheduler(context, preferences).schedule(kind);
        return Result.success();
    }

    private static void showNotification(Context context, OrthodoxPrayersApp app, AppPreferences preferences, String kind) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    local(preferences, "تذكيرات الصلاة", "Prayer reminders", "Ὑπενθυμίσεις προσευχῆς"),
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            channel.setDescription(local(preferences, "تذكيرات اختيارية للصلاة وقراءات اليوم", "Optional prayer and daily-reading reminders", "Προαιρετικὲς ὑπενθυμίσεις"));
            manager.createNotificationChannel(channel);
        }

        Intent intent = new Intent(context, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
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

        Notification.Builder notification = new Notification.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_nav_prayers)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(pendingIntent);
        manager.notify(Math.abs(kind.hashCode()), notification.build());
    }

    private static String local(AppPreferences preferences, String ar, String en, String el) {
        if ("en".equals(preferences.effectiveLanguage())) return en;
        if ("el".equals(preferences.effectiveLanguage())) return el;
        return ar;
    }
}
