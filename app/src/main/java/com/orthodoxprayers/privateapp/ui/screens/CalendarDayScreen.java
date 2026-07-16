package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class CalendarDayScreen extends BaseScreen {
    private final String date;
    public CalendarDayScreen(ScreenHost host, String date) { super(host); this.date = date == null ? "" : date; }

    @Override
    public View createView() {
        UiKit.Page page = page(local("تفاصيل اليوم", "Day details", "Λεπτομέρειες ἡμέρας"), true);
        JSONObject item = findDay();
        if (item == null) {
            add(page.root, centered(local("لا توجد تفاصيل موثوقة لهذا التاريخ داخل الحزمة الحالية.", "No trusted details for this date are included in the current package.", "Δὲν ὑπάρχουν ἔμπιστες λεπτομέρειες γιὰ αὐτὴν τὴν ἡμερομηνία."), 16, ui.colors().secondaryText(), false), 30, 30);
            return page.scroll;
        }
        LinearLayout card = ui.card();
        card.addView(centered("📅  " + date, 21, ui.colors().primaryText(), true));
        addField(card, local("التذكار", "Commemoration", "Μνήμη"), localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), "")));
        addField(card, local("الصيام", "Fasting", "Νηστεία"), localized(item.optJSONObject("status"), localized(item.optJSONObject("fast"), "")));
        JSONObject refs = item.optJSONObject("reading_references");
        if (refs != null) {
            addReference(card, refs.optJSONObject("epistle"), local("الرسالة", "Epistle", "Ἀπόστολος"));
            addReference(card, refs.optJSONObject("gospel"), local("الإنجيل", "Gospel", "Εὐαγγέλιον"));
        }
        add(page.root, card, 14, 16);
        return page.scroll;
    }

    private void addReference(LinearLayout card, JSONObject reading, String label) {
        if (reading == null) return;
        addField(card, label, localized(reading.optJSONObject("reference"), ""));
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 8, 0, 0));
    }

    private JSONObject findDay() {
        if (date.equals(data.dataDate())) return data.today();
        JSONArray upcoming = data.today().optJSONArray("upcoming");
        if (upcoming == null) return null;
        for (int i = 0; i < upcoming.length(); i++) {
            JSONObject item = upcoming.optJSONObject(i);
            if (item != null && date.equals(item.optString("date", ""))) return item;
        }
        return null;
    }
}
