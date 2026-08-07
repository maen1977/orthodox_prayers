package com.orthodoxprayers.privateapp;

import android.app.Application;

import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.appupdate.AppUpdateManager;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.widget.DailyAgendaWidget;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Application-scoped dependency container; prevents duplicate repositories and executors. */
public final class OrthodoxPrayersApp extends Application {
    private AppPreferences preferences;
    private DataRepository repository;
    private UpdateCoordinator updateCoordinator;
    private AppUpdateManager appUpdateManager;
    private final ExecutorService startupMaintenance = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable, "OrthodoxStartupMaintenance");
        thread.setPriority(Thread.MIN_PRIORITY);
        return thread;
    });

    @Override
    public void onCreate() {
        super.onCreate();
        preferences = new AppPreferences(this);
        // A fresh app session always opens the reader at maximum reading space.
        preferences.setReaderControlsExpanded(false);
        repository = new DataRepository(this, preferences);
        updateCoordinator = new UpdateCoordinator(this, preferences, repository);
        appUpdateManager = new AppUpdateManager(this, preferences);
        // None of these maintenance operations are required to draw the first
        // activity frame. Keep Application.onCreate() deterministic and fast so
        // Android never leaves the user staring at the launch window.
        startupMaintenance.execute(() -> {
            updateCoordinator.scheduleDailyRefresh();
            appUpdateManager.schedulePeriodicChecks();
            new ReminderScheduler(this, preferences).scheduleAll();
            DailyAgendaWidget.updateAll(this);
            AppShortcuts.install(this, repository);
        });
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        if (repository != null) repository.releaseOptionalCaches(level);
    }

    public AppPreferences preferences() { return preferences; }
    public DataRepository repository() { return repository; }
    public UpdateCoordinator updateCoordinator() { return updateCoordinator; }
    public AppUpdateManager appUpdateManager() { return appUpdateManager; }
    public void refreshShortcuts() { AppShortcuts.install(this, repository); }
}
