package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
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
        if ("daily".equals(category)) addOfficialDailyPrayerResources(page.root);
        return page.scroll;
    }

    private void addOfficialDailyPrayerResources(LinearLayout root) {
        JSONArray resources = data.officialPrayerResources(preferences.effectiveLanguage());
        if (resources.length() == 0) return;
        TextView heading = centered(local(com.orthodoxprayers.privateapp.R.string.ui_official_daily_prayer_sources_r62), 15, ui.colors().primaryText(), true);
        add(root, heading, 16, 8);
        for (int i = 0; i < resources.length(); i++) {
            JSONObject item = resources.optJSONObject(i);
            if (item == null) continue;
            String url = item.optString("url", "").trim();
            if (url.isEmpty()) continue;
            String title = localized(item.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_prayer_48a8929a));
            String summary = localized(item.optJSONObject("summary"), local(com.orthodoxprayers.privateapp.R.string.ui_official_source_link_only_r62));
            LinearLayout card = ui.actionCard(com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers, title, summary);
            card.setOnClickListener(v -> openOfficialUrl(url));
            add(root, card, 2, 8);
        }
    }

    private void openOfficialUrl(String url) {
        try {
            host.activity().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception error) {
            Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_the_source_link_could_not_be_opened_75a90f8a), Toast.LENGTH_LONG).show();
        }
    }
}
