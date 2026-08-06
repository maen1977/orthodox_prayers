package com.orthodoxprayers.privateapp.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.appupdate.AppUpdateManager;

/** Persistent best-effort GitHub release check. Installation always remains user-approved. */
public final class AppUpdateWorker extends Worker {
    public AppUpdateWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context applicationContext = getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return Result.failure();
        AppUpdateManager.BackgroundResult result =
                ((OrthodoxPrayersApp) applicationContext).appUpdateManager().performBackgroundCheck();
        if (result == AppUpdateManager.BackgroundResult.RETRY && getRunAttemptCount() < 4) {
            return Result.retry();
        }
        return Result.success();
    }
}
