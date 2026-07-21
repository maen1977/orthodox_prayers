package com.orthodoxprayers.privateapp.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.widget.DailyAgendaWidget;

public final class DailyUpdateWorker extends Worker {
    public DailyUpdateWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context applicationContext = getApplicationContext();
        if (!(applicationContext instanceof OrthodoxPrayersApp)) return Result.failure();
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) applicationContext;
        boolean force = getInputData().getBoolean(UpdateCoordinator.INPUT_FORCE, false);

        DataRepository.RefreshOutcome outcome = app.repository().refreshBlocking(force);
        if (outcome.result == DataRepository.RefreshResult.UPDATED
                || outcome.result == DataRepository.RefreshResult.NOT_MODIFIED) {
            app.updateCoordinator().scheduleDailyRefresh();
            DailyAgendaWidget.updateAll(applicationContext);
            return Result.success();
        }

        boolean retryable = DataRepository.isRetryableRefreshMessage(outcome.message);
        if (retryable && getRunAttemptCount() < 8) return Result.retry();

        app.updateCoordinator().scheduleDailyRefresh();
        return Result.failure();
    }
}
