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
        TextView hint = centered(local("اختر الصلاة أو الخدمة لفتح النص الكامل. الشريط السفلي يبقى ظاهرًا للتنقل.",
                "Choose a prayer or service. The bottom navigation remains visible.",
                "Ἐπιλέξτε προσευχή ἢ ἀκολουθία."), 14, ui.colors().secondaryText(), false);
        add(page.root, hint, 12, 8);
        ArrayList<JSONObject> services = data.servicesByCategory(category);
        if (services.isEmpty()) {
            TextView empty = centered(local("لا توجد نصوص في هذا القسم.", "No texts in this section.", "Δεν υπάρχουν κείμενα."), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
        } else {
            for (JSONObject service : services) add(page.root, serviceCard(service), 2, 8);
        }
        return page.scroll;
    }
}
