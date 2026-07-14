package com.orthodoxprayers.privateapp.ui.screens;

import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.ui.AppScreen;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

public abstract class BaseScreen implements AppScreen {
    protected final ScreenHost host;
    protected final UiKit ui;
    protected final DataRepository data;
    protected final AppPreferences preferences;

    protected BaseScreen(ScreenHost host) {
        this.host = host;
        this.ui = host.ui();
        this.data = host.data();
        this.preferences = host.preferences();
    }

    protected UiKit.Page page(String title, boolean back) {
        UiKit.Page page = ui.page();
        page.root.addView(ui.header(title, back, host::goBack), new LinearLayout.LayoutParams(-1, -2));
        return page;
    }

    protected void add(LinearLayout root, View view, int top, int bottom) {
        root.addView(view, ui.margins(-1, -2, 0, top, 0, bottom));
    }

    protected TextView centered(String value, float size, int color, boolean bold) {
        TextView view = ui.text(value, size, color, bold);
        view.setGravity(Gravity.CENTER);
        return view;
    }

    protected String local(String ar, String en, String el) { return data.local(ar, en, el); }
    protected String localized(JSONObject object, String fallback) { return data.localized(object, fallback); }

    protected LinearLayout serviceCard(JSONObject service) {
        LinearLayout card = ui.card();
        card.setClickable(true);
        card.setFocusable(true);
        String title = localized(service.optJSONObject("title"), local("صلاة", "Prayer", "Προσευχή"));
        String summary = localized(service.optJSONObject("summary"), "");
        TextView heading = ui.text(service.optString("icon", "☦") + "  " + title, 18, ui.colors().primaryText(), true);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) heading.setAccessibilityHeading(true);
        card.addView(heading);
        if (!summary.isEmpty()) {
            TextView description = ui.text(summary, 14, ui.colors().secondaryText(), false);
            description.setMaxLines(4);
            card.addView(description, ui.margins(-1, -2, 0, 4, 0, 0));
        }
        card.setContentDescription(title + (summary.isEmpty() ? "" : ". " + summary));
        card.setOnClickListener(v -> host.navigate("reader", service.optString("id")));
        return card;
    }
}
