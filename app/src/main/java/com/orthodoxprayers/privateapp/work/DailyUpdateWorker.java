package com.orthodoxprayers.privateapp.work;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.widget.DailyAgendaWidget;

/** Rebuilds the church day only from assets installed with the application. */
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
        app.updateCoordinator().scheduleDailyRefresh();
        if (outcome.result == DataRepository.RefreshResult.UPDATED
                || outcome.result == DataRepository.RefreshResult.NOT_MODIFIED) {
            DailyAgendaWidget.updateAll(applicationContext);
            return Result.success();
        }

        // Local failures are deterministic (for example, a date outside the bundled
        // 2026–2050 range). Retrying cannot fix them and would waste battery.
        return Result.failure();
    }
}
