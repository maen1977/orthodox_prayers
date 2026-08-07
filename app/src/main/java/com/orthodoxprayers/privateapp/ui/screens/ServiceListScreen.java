package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.ArrayList;

public final class ServiceListScreen extends BaseScreen {
    private final String category;
    private final String title;

    public ServiceListScreen(ScreenHost host, String category, String title) {
        super(host);
        this.category = category;
        this.title = title;
    }

    @Override
    public View createView() {
        UiKit.Page page = page(title, true);
        String hintText = "church_service".equals(category) ? local(com.orthodoxprayers.privateapp.R.string.ui_church_service_hint) : local(com.orthodoxprayers.privateapp.R.string.ui_choose_a_prayer_or_service_the_bottom_navigation_daa89d81);
        TextView hint = centered(hintText, 14, ui.colors().secondaryText(), false);
        add(page.root, hint, 12, 8);
        ArrayList<JSONObject> services = data.servicesByCategory(category);
        if (services.isEmpty()) {
            TextView empty = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_texts_in_this_section_a43f561b), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
        } else {
            for (JSONObject service : services) add(page.root, serviceCard(service), 2, 8);
        }
        return page.scroll;
    }
}
