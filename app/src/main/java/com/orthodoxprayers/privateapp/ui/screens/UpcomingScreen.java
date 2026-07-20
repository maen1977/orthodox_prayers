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
        UiKit.Page page = page(local("الأيام القادمة", "Upcoming Days", "Ἐπόμενες Ἡμέρες"), true);
        TextView note = centered(local("تظهر حالة الصيام ومراجع القراءات لكل يوم دون إعادة استخدام بيانات يوم سابق.",
                "Each day has its own fasting profile and reading references.",
                "Κάθε ἡμέρα ἔχει δικό της πρόγραμμα νηστείας καὶ ἀναγνωσμάτων."), 13, ui.colors().secondaryText(), false);
        add(page.root, note, 12, 8);
        JSONArray upcoming = data.today().optJSONArray("upcoming");
        if (upcoming != null) {
            for (int i = 0; i < upcoming.length(); i++) {
                JSONObject item = upcoming.optJSONObject(i);
                if (item != null) add(page.root, dayCard(item), 2, 7);
            }
        }
        JSONObject todayFasting = data.today().optJSONObject("fasting");
        JSONObject guidance = todayFasting == null ? null : todayFasting.optJSONObject("guidance");
        if (guidance != null) {
            LinearLayout reminder = ui.card();
            String spiritual = localized(guidance.optJSONObject("spiritual_note"), "");
            String health = localized(guidance.optJSONObject("health_note"), "");
            if (!spiritual.isEmpty()) reminder.addView(ui.text("🙏  " + spiritual, 13, ui.colors().secondaryText(), false));
            if (!health.isEmpty()) reminder.addView(ui.text("⚕  " + health, 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 6, 0, 0));
            add(page.root, reminder, 8, 16);
        }
        return page.scroll;
    }

    private LinearLayout dayCard(JSONObject item) {
        LinearLayout card = ui.card();
        String day = localized(item.optJSONObject("day"), item.optString("date", ""));
        TextView heading = ui.text("📅  " + day, 16, ui.colors().primaryText(), true);
        card.addView(heading);
        card.addView(ui.text(localized(item.optJSONObject("status"), ""), 14, ui.colors().accentText(), true), ui.margins(-1, -2, 0, 4, 0, 0));
        addFastingGuide(card, item.optJSONObject("fasting"), false);
        String feast = localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), ""));
        if (!feast.isEmpty()) card.addView(ui.text(feast, 13, ui.colors().secondaryText(), false));
        JSONObject refs = item.optJSONObject("reading_references");
        addReference(card, refs, "epistle", "📜 " + local("الرسالة: ", "Epistle: ", "Ἀπόστολος: "));
        addReference(card, refs, "gospel", "📖 " + local("الإنجيل: ", "Gospel: ", "Εὐαγγέλιον: "));
        card.setContentDescription(day + ". " + feast);
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
