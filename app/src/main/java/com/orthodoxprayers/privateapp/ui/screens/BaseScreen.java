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

    protected void addFastingGuide(LinearLayout card, JSONObject fasting, boolean includeNotes) {
        // Ordinary days intentionally show only “No fast”; food permissions and
        // explanatory paragraphs are useful only when a fasting rule applies.
        if (!isFastingDay(fasting)) return;
        JSONObject guidance = fasting.optJSONObject("guidance");
        if (guidance == null) return;

        addGuideLine(card, "✓", localized(guidance.optJSONObject("allowed_summary"), ""), true);
        addGuideLine(card, "✕", localized(guidance.optJSONObject("forbidden_summary"), ""), true);
        addGuideLine(card, "•", localized(guidance.optJSONObject("duration"), ""), false);

        JSONObject abstinence = fasting.optJSONObject("abstinence");
        if (abstinence != null && (abstinence.optBoolean("applies", false) || includeNotes)) {
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

        if (includeNotes) {
            addGuideLine(card, "ℹ", localized(guidance.optJSONObject("beginner_explanation"), ""), false);
            addGuideLine(card, "•", localized(guidance.optJSONObject("spiritual_note"), ""), false);
            addGuideLine(card, "•", localized(guidance.optJSONObject("health_note"), ""), false);
        }
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

    protected boolean isFastingDay(JSONObject fasting) {
        if (fasting == null || fasting.length() == 0) return false;
        if (fasting.has("is_fast")) return fasting.optBoolean("is_fast", false);
        return !"fast_free".equals(fasting.optString("code", ""));
    }

    /**
     * Produce the concise fasting label shown to ordinary users. Weekly Wednesday
     * and Friday fasts name the actual weekday instead of the generic
     * “Wednesday or Friday” rule label. Fast-free days always use one plain label.
     */
    protected String fastingDisplayTitle(JSONObject day, String fallbackDate) {
        JSONObject fasting = day == null ? null : day.optJSONObject("fasting");
        if (fasting != null && fasting.length() > 0) {
            if (!isFastingDay(fasting)) {
                return local(com.orthodoxprayers.privateapp.R.string.ui_no_fast_plain);
            }
            JSONObject verification = fasting.optJSONObject("verification");
            String rule = verification == null ? "" : verification.optString("rule", "");
            if ("weekly_wednesday_friday".equals(rule)) {
                DayOfWeek weekday = parseWeekday(dayDate(day, fallbackDate));
                String season = weekday == DayOfWeek.WEDNESDAY
                        ? local(com.orthodoxprayers.privateapp.R.string.ui_wednesday_fast)
                        : weekday == DayOfWeek.FRIDAY
                        ? local(com.orthodoxprayers.privateapp.R.string.ui_friday_fast)
                        : localized(fasting.optJSONObject("season"), "");
                String level = localized(fasting.optJSONObject("level"), "");
                if (!season.isEmpty()) return level.isEmpty() ? season : season + " — " + level;
            }
            String title = localized(fasting.optJSONObject("title"), "");
            if (!title.isEmpty()) return title;
        }

        String raw = day == null ? "" : localized(day.optJSONObject("status"),
                localized(day.optJSONObject("fast"), ""));
        if (looksFastFree(raw)) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_no_fast_plain);
        }
        return raw.isEmpty()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_unavailable_24f3ca2e)
                : raw;
    }

    protected String displayableCommemoration(JSONObject day) {
        if (day == null) return "";
        String status = day.optString("daily_proper_status", "").trim();
        if (status.startsWith("UNAVAILABLE") || status.startsWith("PENDING")) return "";
        String value = localized(day.optJSONObject("feast"), localized(day.optJSONObject("note"), ""));
        return isCommemorationPlaceholder(value) ? "" : value;
    }

    private String dayDate(JSONObject day, String fallbackDate) {
        if (day != null) {
            String value = day.optString("date_iso", day.optString("date", "")).trim();
            if (!value.isEmpty()) return value;
        }
        return fallbackDate == null ? "" : fallbackDate.trim();
    }

    private DayOfWeek parseWeekday(String date) {
        try { return LocalDate.parse(date).getDayOfWeek(); }
        catch (Exception ignored) { return null; }
    }

    private boolean looksFastFree(String value) {
        String normalized = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        return normalized.equals("لا صوم")
                || normalized.equals("لا يوجد صوم")
                || normalized.equals("no fast")
                || normalized.equals("χωρὶς νηστεία")
                || normalized.equals("χωρίς νηστεία");
    }

    private boolean isCommemorationPlaceholder(String value) {
        if (value == null || value.trim().isEmpty()) return true;
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        return normalized.contains("غير منشور")
                || normalized.contains("تعذر التحقق من تذكار")
                || normalized.contains("تذكار اليوم بحسب التقويم")
                || normalized.contains("pending ecclesiastical review")
                || normalized.contains("could not verify the commemoration")
                || normalized.contains("today’s commemoration according")
                || normalized.contains("today's commemoration according")
                || normalized.contains("δὲν δημοσιεύεται")
                || normalized.contains("δεν δημοσιεύεται")
                || normalized.contains("ἡ σημερινὴ μνήμη κατὰ")
                || normalized.contains("η σημερινή μνήμη κατά");
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
