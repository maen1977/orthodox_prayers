package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;

public final class PrayerHubScreen extends BaseScreen {
    public PrayerHubScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_prayers_3a9327c4), false);
        TextView hint = centered(local(com.orthodoxprayers.privateapp.R.string.ui_daily_and_basic_prayers_are_available_here_botto_36b71462), 14, ui.colors().secondaryText(), false);
        add(page.root, hint, 12, 6);
        addCategory(page, "daily", local(com.orthodoxprayers.privateapp.R.string.ui_daily_prayers_ef97d9fd));
        addCategory(page, "basic", local(com.orthodoxprayers.privateapp.R.string.ui_basic_prayers_6f2ed521));
        addCategory(page, "communion", local(com.orthodoxprayers.privateapp.R.string.ui_holy_communion_prayers_e14c166c));
        return page.scroll;
    }

    private void addCategory(UiKit.Page page, String category, String title) {
        page.root.addView(ui.sectionTitle(title));
        ArrayList<JSONObject> services = data.servicesByCategory(category);
        if (services.isEmpty()) {
            TextView empty = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_texts_in_this_section_a43f561b), 14, ui.colors().secondaryText(), false);
            add(page.root, empty, 4, 8);
            return;
        }
        for (JSONObject service : services) add(page.root, serviceCard(service), 2, 8);
    }
}
