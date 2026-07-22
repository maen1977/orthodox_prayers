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

import org.json.JSONArray;
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

    protected void addFastingGuide(LinearLayout card, JSONObject fasting, boolean includeNotes) {
        if (fasting == null || fasting.length() == 0) return;
        JSONObject guidance = fasting.optJSONObject("guidance");
        if (guidance == null) return;

        addGuideLine(card, local("المسموح", "Allowed", "Ἐπιτρέπεται"), localized(guidance.optJSONObject("allowed_summary"), ""), true);
        addGuideLine(card, local("الممنوع", "Not allowed", "Ἀπαγορεύεται"), localized(guidance.optJSONObject("forbidden_summary"), ""), true);
        addGuideLine(card, local("المدة", "Duration", "Διάρκεια"), localized(guidance.optJSONObject("duration"), ""), false);

        JSONObject abstinence = fasting.optJSONObject("abstinence");
        if (abstinence != null && (abstinence.optBoolean("applies", false) || includeNotes)) {
            String abstinenceText = localized(abstinence.optJSONObject("end_condition"), "");
            String start = abstinence.optString("start_time", "").trim();
            String end = abstinence.optString("end_time", "").trim();
            if (!start.isEmpty() || !end.isEmpty()) {
                String interval = local("من " + start + " إلى " + end, "From " + start + " to " + end, "Ἀπὸ " + start + " ἕως " + end);
                abstinenceText = interval + (abstinenceText.isEmpty() ? "" : "\n" + abstinenceText);
            }
            String label = local("الصوم الانقطاعي", "Total abstinence", "Πλήρης ἀποχή");
            if (!abstinenceText.isEmpty()) addGuideLine(card, label, abstinenceText, false);
        }

        if (includeNotes) {
            addGuideLine(card, local("توضيح", "Guidance", "Ὁδηγία"), localized(guidance.optJSONObject("beginner_explanation"), ""), false);
            addGuideLine(card, local("إرشاد روحي", "Spiritual guidance", "Πνευματικὴ ὁδηγία"), localized(guidance.optJSONObject("spiritual_note"), ""), false);
            addGuideLine(card, local("تنبيه صحي", "Health note", "Σημείωση ὑγείας"), localized(guidance.optJSONObject("health_note"), ""), false);
        }
    }

    private void addGuideLine(LinearLayout card, String label, String value, boolean bold) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ": " + value, 13, bold ? ui.colors().primaryText() : ui.colors().secondaryText(), bold);
        card.addView(text, ui.margins(-1, -2, 0, 6, 0, 0));
    }


    /**
     * Compact, symbol-first food rules for small day cards. The method deliberately
     * renders only fasting days so ordinary days stay visually light. A check mark
     * always means permitted and a cross always means forbidden; color is never the
     * only carrier of meaning.
     */
    protected String addCompactFastingItems(LinearLayout card, JSONObject fasting) {
        if (fasting == null || !fasting.optBoolean("is_fast", false)) return "";
        JSONArray items = fasting.optJSONArray("items");
        if (items == null || items.length() == 0) return "";

        StringBuilder visible = new StringBuilder();
        StringBuilder accessible = new StringBuilder();
        for (int index = 0; index < items.length(); index++) {
            JSONObject item = items.optJSONObject(index);
            if (item == null) continue;
            String label = localized(item.optJSONObject("label"), item.optString("key", ""));
            if (label.isEmpty()) continue;
            boolean allowed = item.optBoolean("allowed", false);
            String marker = allowed ? "✓" : "✕";
            String word = allowed
                    ? local("مسموح", "allowed", "ἐπιτρέπεται")
                    : local("ممنوع", "forbidden", "ἀπαγορεύεται");
            String token = item.optString("icon", "•") + " " + label + " " + marker;
            if (visible.length() > 0) visible.append(index % 2 == 0 ? "\n" : "   ");
            visible.append(token);
            if (accessible.length() > 0) accessible.append(". ");
            accessible.append(label).append(": ").append(word);
        }
        if (visible.length() == 0) return "";

        TextView legend = ui.text(
                local("✓ مسموح   ✕ ممنوع", "✓ Allowed   ✕ Forbidden", "✓ Ἐπιτρέπεται   ✕ Ἀπαγορεύεται"),
                10,
                ui.colors().secondaryText(),
                true
        );
        card.addView(legend, ui.margins(-1, -2, 0, 4, 0, 1));
        TextView rules = ui.text(visible.toString(), 11, ui.colors().primaryText(), true);
        rules.setContentDescription(accessible.toString());
        card.addView(rules, ui.margins(-1, -2, 0, 2, 0, 3));
        return accessible.toString();
    }

    protected LinearLayout serviceCard(JSONObject service) {
        LinearLayout card = ui.card();
        card.setClickable(true);
        card.setFocusable(true);
        card.setBackground(ui.ripple(ui.colors().card(), ui.colors().border(), 18, ui.colors().ripple()));
        String title = localized(service.optJSONObject("title"), local("صلاة", "Prayer", "Προσευχή"));
        String summary = localized(service.optJSONObject("summary"), "");
        TextView heading = ui.text(title, 18, ui.colors().primaryText(), true);
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
