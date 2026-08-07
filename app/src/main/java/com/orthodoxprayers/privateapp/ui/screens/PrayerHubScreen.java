package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

public final class PrayerHubScreen extends BaseScreen {
    public PrayerHubScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_prayers_3a9327c4), false);
        TextView hint = centered(local(com.orthodoxprayers.privateapp.R.string.ui_daily_and_basic_prayers_are_available_here_botto_36b71462), 14, ui.colors().secondaryText(), false);
        add(page.root, hint, 12, 8);
        addCategory(page, "daily", local(com.orthodoxprayers.privateapp.R.string.ui_daily_prayers_ef97d9fd));
        addCategory(page, "basic", local(com.orthodoxprayers.privateapp.R.string.ui_basic_prayers_6f2ed521));
        addCategory(page, "communion", local(com.orthodoxprayers.privateapp.R.string.ui_holy_communion_prayers_e14c166c));
        addCategory(page, "church_service", local(com.orthodoxprayers.privateapp.R.string.ui_church_service_section));
        return page.scroll;
    }

    private void addCategory(UiKit.Page page, String category, String title) {
        int icon = "daily".equals(category)
                ? com.orthodoxprayers.privateapp.R.drawable.ic_action_calendar
                : ("communion".equals(category) || "church_service".equals(category))
                ? com.orthodoxprayers.privateapp.R.drawable.ic_action_liturgy
                : com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers;
        LinearLayout card = ui.actionCard(icon, title, "");
        card.setOnClickListener(v -> host.navigate("prayer_category", category));
        add(page.root, card, 4, 8);
    }
}
