package com.orthodoxprayers.privateapp.ui.screens;

import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.CommemorationDisplayPolicy;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.ui.AppScreen;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.Locale;

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

    protected String local(int resourceId) { return data.local(resourceId); }
    protected String localFormat(int resourceId, Object... arguments) { return data.localFormat(resourceId, arguments); }
    protected String localized(JSONObject object, String fallback) { return data.localized(object, fallback); }

    protected boolean isFastingDay(JSONObject fasting) {
        return fasting != null && fasting.optBoolean("is_fast", false);
    }

    protected String fastingDisplayTitle(JSONObject day, String isoDate) {
        JSONObject fasting = day == null ? null : day.optJSONObject("fasting");
        if (!isFastingDay(fasting)) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_no_fast_plain);
        }

        String title = localized(fasting.optJSONObject("title"), "");
        JSONObject verification = fasting.optJSONObject("verification");
        String rule = verification == null ? "" : verification.optString("rule", "");
        if ("weekly_wednesday_friday".equals(rule)) {
            String dateValue = isoDate == null || isoDate.trim().isEmpty()
                    ? day.optString("date_iso", day.optString("date", ""))
                    : isoDate;
            try {
                DayOfWeek weekday = LocalDate.parse(dateValue).getDayOfWeek();
                String weekdayTitle = "";
                if (weekday == DayOfWeek.WEDNESDAY) {
                    weekdayTitle = local(com.orthodoxprayers.privateapp.R.string.ui_wednesday_fast);
                } else if (weekday == DayOfWeek.FRIDAY) {
                    weekdayTitle = local(com.orthodoxprayers.privateapp.R.string.ui_friday_fast);
                }
                if (!weekdayTitle.isEmpty()) {
                    String level = localized(fasting.optJSONObject("level"), "");
                    return level.isEmpty() ? weekdayTitle : weekdayTitle + " — " + level;
                }
            } catch (Exception ignored) {
                // Keep the verified localized title when a legacy payload has no ISO date.
            }
        }

        if (!title.isEmpty()) return title;
        String status = day == null ? "" : localized(day.optJSONObject("status"), localized(day.optJSONObject("fast"), ""));
        return status.isEmpty()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_fasting_f1b1605d)
                : status;
    }

    protected String displayableCommemoration(JSONObject day) {
        return CommemorationDisplayPolicy.displayText(day, data::localizedValue);
    }

    protected void addFastingGuide(LinearLayout card, JSONObject fasting, boolean includeNotes) {
        if (!isFastingDay(fasting)) return;
        JSONObject guidance = fasting.optJSONObject("guidance");
        if (guidance == null) {
            addGuideLine(card, "•", localized(fasting.optJSONObject("detail"), ""), false);
            addAbstinenceGuide(card, fasting);
            return;
        }

        addGuideLine(card, "✓", localized(guidance.optJSONObject("allowed_summary"), ""), true);
        addGuideLine(card, "✕", localized(guidance.optJSONObject("forbidden_summary"), ""), true);
        addGuideLine(card, "•", localized(guidance.optJSONObject("duration"), ""), false);
        addAbstinenceGuide(card, fasting);

        if (includeNotes) {
            addGuideLine(card, "ℹ", localized(guidance.optJSONObject("beginner_explanation"), ""), false);
            addGuideLine(card, "•", localized(guidance.optJSONObject("spiritual_note"), ""), false);
            addGuideLine(card, "•", localized(guidance.optJSONObject("health_note"), ""), false);
        }
    }

    private void addAbstinenceGuide(LinearLayout card, JSONObject fasting) {
        JSONObject abstinence = fasting.optJSONObject("abstinence");
        if (abstinence == null || !abstinence.optBoolean("applies", false)) return;
        String abstinenceText = localized(abstinence.optJSONObject("end_condition"), "");
        String start = abstinence.optString("start_time", "").trim();
        String end = abstinence.optString("end_time", "").trim();
        if (!start.isEmpty() || !end.isEmpty()) {
            String interval = localFormat(com.orthodoxprayers.privateapp.R.string.ui_fasting_interval_format, start, end);
            abstinenceText = interval + (abstinenceText.isEmpty() ? "" : "\n" + abstinenceText);
        }
        String label = local(com.orthodoxprayers.privateapp.R.string.ui_total_abstinence_4bf885f8);
        if (!abstinenceText.isEmpty()) addGuideLine(card, "⏳", label + ": " + abstinenceText, false);
    }

    private void addGuideLine(LinearLayout card, String icon, String value, boolean bold) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(icon + "  " + value, 13, bold ? ui.colors().primaryText() : ui.colors().secondaryText(), bold);
        card.addView(text, ui.margins(-1, -2, 0, 5, 0, 0));
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
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_allowed_f3016067)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_forbidden_8f73bf02);
            String token = item.optString("icon", "•") + " " + label + " " + marker;
            if (visible.length() > 0) visible.append(index % 2 == 0 ? "\n" : "   ");
            visible.append(token);
            if (accessible.length() > 0) accessible.append(". ");
            accessible.append(label).append(": ").append(word);
        }
        if (visible.length() == 0) return "";

        TextView legend = ui.text(
                local(com.orthodoxprayers.privateapp.R.string.ui_allowed_forbidden_3e7d8352),
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
        String title = localized(service.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_prayer_48a8929a));
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
