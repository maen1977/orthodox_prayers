package com.orthodoxprayers.privateapp.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;

/** Restores the network-free 00:03 Amman local refresh after system changes. */
public final class ScheduleRestoreReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Context applicationContext = context.getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return;
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) applicationContext;
        app.updateCoordinator().scheduleDailyRefresh();
        app.appUpdateManager().schedulePeriodicChecks();
    }
}
