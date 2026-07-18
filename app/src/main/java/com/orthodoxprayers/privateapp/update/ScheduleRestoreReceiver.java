package com.orthodoxprayers.privateapp.update;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;

/** Restores the 00:00 schedule after reboot, app upgrade, or clock/time-zone changes. */
public final class ScheduleRestoreReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Context applicationContext = context.getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return;
        ((OrthodoxPrayersApp) applicationContext).updateCoordinator().scheduleMidnightRefresh();
    }
}
