package com.orthodoxprayers.privateapp.ui;

import android.view.View;

public interface AppScreen {
    View createView();
    default void onVisible() {}
    default void onHidden() {}
}
