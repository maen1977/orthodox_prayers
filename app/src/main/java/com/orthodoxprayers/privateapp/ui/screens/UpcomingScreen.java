package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class UpcomingScreen extends BaseScreen {
    public UpcomingScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_upcoming_days_a15c452f), true);
        TextView note = centered(local(com.orthodoxprayers.privateapp.R.string.ui_the_signed_package_keeps_today_and_the_next_seve_8ba1a6f0), 13, ui.colors().secondaryText(), false);
        add(page.root, note, 12, 8);
        JSONArray upcoming = data.rollingWeekDays();
        if (upcoming.length() == 0) upcoming = data.today().optJSONArray("upcoming");
        if (upcoming != null) {
            for (int i = 0; i < upcoming.length(); i++) {
                JSONObject item = upcoming.optJSONObject(i);
                if (item == null) continue;
                String itemDate = item.optString("date_iso", item.optString("date", ""));
                if (itemDate.equals(data.currentAmmanDate())) continue;
                add(page.root, dayCard(item), 2, 7);
            }
        }
        JSONObject todayFasting = data.today().optJSONObject("fasting");
        JSONObject guidance = todayFasting == null ? null : todayFasting.optJSONObject("guidance");
        if (guidance != null) {
            LinearLayout reminder = ui.card();
            String spiritual = localized(guidance.optJSONObject("spiritual_note"), "");
            String health = localized(guidance.optJSONObject("health_note"), "");
            if (!spiritual.isEmpty()) reminder.addView(ui.text(spiritual, 13, ui.colors().secondaryText(), false));
            if (!health.isEmpty()) reminder.addView(ui.text(health, 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 6, 0, 0));
            add(page.root, reminder, 8, 16);
        }
        return page.scroll;
    }

    private LinearLayout dayCard(JSONObject item) {
        LinearLayout card = ui.card();
        String itemDate = item.optString("date_iso", item.optString("date", ""));
        String day = localized(item.optJSONObject("day"), localized(item.optJSONObject("date_label"), itemDate));
        TextView heading = ui.text(day, 16, ui.colors().primaryText(), true);
        card.addView(heading);
        card.addView(ui.text(localized(item.optJSONObject("status"), ""), 14, ui.colors().accentText(), true), ui.margins(-1, -2, 0, 4, 0, 0));
        JSONObject fasting = item.optJSONObject("fasting");
        addCompactFastingItems(card, fasting);
        addFastingGuide(card, fasting, false);
        String feast = localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), ""));
        if (!feast.isEmpty()) card.addView(ui.text(feast, 13, ui.colors().secondaryText(), false));
        JSONObject refs = item.optJSONObject("reading_references");
        addReference(card, refs, "epistle", local(com.orthodoxprayers.privateapp.R.string.ui_epistle_dd82c199));
        addReference(card, refs, "gospel", local(com.orthodoxprayers.privateapp.R.string.ui_gospel_68845cc5));
        card.setContentDescription(day + ". " + feast);
        if (!itemDate.isEmpty()) {
            card.setClickable(true);
            card.setFocusable(true);
            card.setOnClickListener(v -> host.navigate("calendar_day", itemDate));
        }
        return card;
    }

    private void addReference(LinearLayout card, JSONObject refs, String kind, String prefix) {
        if (refs == null) return;
        JSONObject item = refs.optJSONObject(kind);
        if (item == null) return;
        String reference = localized(item.optJSONObject("reference"), "");
        if (!reference.isEmpty()) card.addView(ui.text(prefix + reference, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
    }
}
