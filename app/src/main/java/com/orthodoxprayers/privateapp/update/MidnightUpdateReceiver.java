package com.orthodoxprayers.privateapp.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;

/** Wakes at 00:00 Amman time, queues the verified refresh, then schedules tomorrow. */
public final class MidnightUpdateReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Context applicationContext = context.getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return;
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) applicationContext;
        app.updateCoordinator().scheduleMidnightRefresh();
        app.updateCoordinator().enqueueMidnightRefresh();
    }
}
