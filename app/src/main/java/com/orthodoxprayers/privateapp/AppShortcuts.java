package com.orthodoxprayers.privateapp;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ShortcutInfo;
import android.content.pm.ShortcutManager;
import android.graphics.drawable.Icon;

import java.util.Arrays;

/** Lightweight launcher shortcuts. No background service or extra dependency is required. */
public final class AppShortcuts {
    private AppShortcuts() {}

    public static void install(Context context, com.orthodoxprayers.privateapp.data.DataRepository data) {
        if (context == null || data == null) return;
        ShortcutManager manager = context.getSystemService(ShortcutManager.class);
        if (manager == null) return;

        ShortcutInfo readings = shortcut(
                context,
                "daily_readings",
                data.local(R.string.ui_shortcut_daily_readings_r43),
                R.drawable.ic_action_readings,
                "readings",
                null
        );
        ShortcutInfo liturgy = shortcut(
                context,
                "divine_liturgy",
                data.local(R.string.ui_shortcut_divine_liturgy_r43),
                R.drawable.ic_action_liturgy,
                "liturgy",
                null
        );
        ShortcutInfo morning = shortcut(
                context,
                "morning_prayer",
                data.local(R.string.ui_shortcut_morning_prayer_r43),
                R.drawable.ic_action_prayers,
                "reader",
                "morning_prayer"
        );
        try {
            manager.setDynamicShortcuts(Arrays.asList(readings, liturgy, morning));
        } catch (RuntimeException ignored) {
            // Launcher implementations may reject updates transiently. App startup must continue.
        }
    }

    private static ShortcutInfo shortcut(
            Context context,
            String id,
            String label,
            int iconResource,
            String screen,
            String argument
    ) {
        Intent intent = new Intent(context, MainActivity.class)
                .setAction(Intent.ACTION_VIEW)
                .putExtra(MainActivity.EXTRA_SCREEN, screen);
        if (argument != null && !argument.isEmpty()) {
            intent.putExtra(MainActivity.EXTRA_ARGUMENT, argument);
        }
        return new ShortcutInfo.Builder(context, id)
                .setShortLabel(label)
                .setLongLabel(label)
                .setIcon(Icon.createWithResource(context, iconResource))
                .setIntent(intent)
                .build();
    }
}
