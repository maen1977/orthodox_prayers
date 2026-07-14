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
        UiKit.Page page = page(local("الصلوات", "Prayers", "Προσευχές"), false);
        TextView hint = centered(local("الصلوات اليومية والصلوات الأساسية متاحة هنا، ويظل شريط التنقل ظاهرًا أسفل الشاشة.",
                "Daily and basic prayers are available here; bottom navigation remains visible.",
                "Καθημερινὲς καὶ βασικὲς προσευχές."), 14, ui.colors().secondaryText(), false);
        add(page.root, hint, 12, 6);
        addCategory(page, "daily", local("الصلوات اليومية", "Daily prayers", "Καθημερινὲς προσευχές"));
        addCategory(page, "basic", local("صلوات أساسية", "Basic prayers", "Βασικὲς προσευχές"));
        return page.scroll;
    }

    private void addCategory(UiKit.Page page, String category, String title) {
        page.root.addView(ui.sectionTitle(title));
        ArrayList<JSONObject> services = data.servicesByCategory(category);
        if (services.isEmpty()) {
            TextView empty = centered(local("لا توجد نصوص في هذا القسم.", "No texts in this section.", "Δεν υπάρχουν κείμενα."), 14, ui.colors().secondaryText(), false);
            add(page.root, empty, 4, 8);
            return;
        }
        for (JSONObject service : services) add(page.root, serviceCard(service), 2, 8);
    }
}
