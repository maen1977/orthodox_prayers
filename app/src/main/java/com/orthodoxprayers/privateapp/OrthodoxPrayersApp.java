package com.orthodoxprayers.privateapp;

import android.app.Application;

import com.orthodoxprayers.privateapp.data.DailyDataStore;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.data.DataSignatureVerifier;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;

/** Application-scoped dependency container; prevents duplicate repositories and executors. */
public final class OrthodoxPrayersApp extends Application {
    private AppPreferences preferences;
    private DataRepository repository;
    private UpdateCoordinator updateCoordinator;

    @Override
    public void onCreate() {
        super.onCreate();
        preferences = new AppPreferences(this);
        DailyDataStore dataStore = new DailyDataStore(this);
        DataSignatureVerifier signatureVerifier = new DataSignatureVerifier(this);
        repository = new DataRepository(this, preferences, dataStore, signatureVerifier);
        updateCoordinator = new UpdateCoordinator(this, preferences, repository);
        updateCoordinator.schedulePeriodicRefresh();
        updateCoordinator.scheduleDailyAmmanRefreshes();
        new ReminderScheduler(this, preferences).scheduleAll();
    }

    public AppPreferences preferences() { return preferences; }
    public DataRepository repository() { return repository; }
    public UpdateCoordinator updateCoordinator() { return updateCoordinator; }
}
