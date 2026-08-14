package com.orthodoxprayers.privateapp.update;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import com.orthodoxprayers.privateapp.work.ChurchDirectorySyncWorker;

import java.util.concurrent.TimeUnit;

/** Schedules the optional network-backed weekly church-directory verification. */
public final class ChurchDirectorySchedule {
    private static final String UNIQUE_WORK = "orthodox-church-directory-weekly-sync-v1";
    private static final String TAG = "orthodox-church-directory-sync";

    private ChurchDirectorySchedule() {}

    public static void schedule(Context context) {
        Context appContext = context.getApplicationContext();
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                ChurchDirectorySyncWorker.class, 7, TimeUnit.DAYS)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
                .addTag(TAG)
                .build();
        WorkManager.getInstance(appContext).enqueueUniquePeriodicWork(
                UNIQUE_WORK,
                androidx.work.ExistingPeriodicWorkPolicy.KEEP,
                request
        );
    }
}
