package com.orthodoxprayers.privateapp.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.data.ChurchDirectorySync;
import com.orthodoxprayers.privateapp.data.DataRepository;

/** Checks official directory sources weekly without deleting a last-good snapshot. */
public final class ChurchDirectorySyncWorker extends Worker {
    public ChurchDirectorySyncWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context applicationContext = getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return Result.failure();
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) applicationContext;
        DataRepository repository = app.repository();
        long now = System.currentTimeMillis();
        ChurchDirectorySync.Result result = ChurchDirectorySync.synchronize(repository.churchDirectorySnapshot());
        if (result.success && result.payload != null && repository.installChurchDirectorySnapshot(result.payload)) {
            app.preferences().recordChurchDirectorySync(true,
                    result.message + ":sources=" + result.available + "/" + result.checked
                            + ",records=" + result.recordsObserved
                            + ",updated=" + result.recordsUpdated, now);
            return Result.success();
        }
        app.preferences().recordChurchDirectorySync(false, result.message, now);
        return result.retryable ? Result.retry() : Result.failure();
    }
}
