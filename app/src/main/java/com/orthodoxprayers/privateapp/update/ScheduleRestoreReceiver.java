package com.orthodoxprayers.privateapp.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;

/** Restores the 01:00 and 06:00 Amman WorkManager schedules after system changes. */
public final class ScheduleRestoreReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Context applicationContext = context.getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return;
        ((OrthodoxPrayersApp) applicationContext).updateCoordinator().scheduleDailyRefresh();
    }
}
