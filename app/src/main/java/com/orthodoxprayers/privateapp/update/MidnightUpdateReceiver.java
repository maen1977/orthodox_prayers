package com.orthodoxprayers.privateapp.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;

/** Legacy receiver retained only so upgrades can safely handle a previously queued alarm. */
public final class MidnightUpdateReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Context applicationContext = context.getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return;
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) applicationContext;
        app.updateCoordinator().scheduleDailyRefresh();
        app.updateCoordinator().enqueueMidnightRefresh();
    }
}
