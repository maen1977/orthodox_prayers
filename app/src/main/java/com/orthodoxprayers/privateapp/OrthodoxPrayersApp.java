package com.orthodoxprayers.privateapp;

import android.app.Application;

import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.widget.DailyAgendaWidget;

/** Application-scoped dependency container; prevents duplicate repositories and executors. */
public final class OrthodoxPrayersApp extends Application {
    private AppPreferences preferences;
    private DataRepository repository;
    private UpdateCoordinator updateCoordinator;

    @Override
    public void onCreate() {
        super.onCreate();
        preferences = new AppPreferences(this);
        repository = new DataRepository(this, preferences);
        updateCoordinator = new UpdateCoordinator(this, preferences, repository);
        updateCoordinator.scheduleDailyRefresh();
        new ReminderScheduler(this, preferences).scheduleAll();
        DailyAgendaWidget.updateAll(this);
    }

    public AppPreferences preferences() { return preferences; }
    public DataRepository repository() { return repository; }
    public UpdateCoordinator updateCoordinator() { return updateCoordinator; }
}
