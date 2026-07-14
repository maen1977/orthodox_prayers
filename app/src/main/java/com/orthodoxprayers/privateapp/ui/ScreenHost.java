package com.orthodoxprayers.privateapp.ui;

import android.app.Activity;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.DataRepository;

import org.json.JSONObject;

public interface ScreenHost {
    Activity activity();
    UiKit ui();
    DataRepository data();
    AppPreferences preferences();
    void navigate(String screenId, String argument);
    void openReading(JSONObject reading);
    void goBack();
    void refreshData();
    String currentScreenId();
}
