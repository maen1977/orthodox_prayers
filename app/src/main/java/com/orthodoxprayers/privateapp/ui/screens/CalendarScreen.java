package com.orthodoxprayers.privateapp.ui.screens;

import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.TextStyle;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Monthly calendar backed by the signed nine-day package plus the compact 2026–2050 offline index. */
public final class CalendarScreen extends BaseScreen {
    private static final YearMonth MIN_MONTH = YearMonth.of(2026, 1);
    private static final YearMonth MAX_MONTH = YearMonth.of(2050, 12);
    private final YearMonth month;

    public CalendarScreen(ScreenHost host, String argument) {
        super(host);
        YearMonth parsed;
        try { parsed = argument == null || argument.isEmpty() ? YearMonth.now() : YearMonth.parse(argument); }
        catch (Exception ignored) { parsed = YearMonth.now(); }
        if (parsed.isBefore(MIN_MONTH)) parsed = MIN_MONTH;
        if (parsed.isAfter(MAX_MONTH)) parsed = MAX_MONTH;
        month = parsed;
    }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_church_calendar_54dcd19b), true);
        addMonthNavigation(page.root);
        add(page.root, ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_the_annual_index_stays_lightweight_while_the_sig_deed927c)), 4, 10);
        addCalendarGrid(page.root);
        addKnownDays(page.root);
        return page.scroll;
    }

    private void addMonthNavigation(LinearLayout root) {
        LinearLayout row = ui.row();
        Button previous = ui.smallButton(preferences.isRtl() ? "→" : "←", false);
        previous.setEnabled(month.isAfter(MIN_MONTH));
        previous.setOnClickListener(v -> host.navigate("calendar", month.minusMonths(1).toString()));
        row.addView(previous, ui.weight(44));

        Locale locale = "ar".equals(preferences.effectiveLanguage()) ? new Locale("ar")
                : "el".equals(preferences.effectiveLanguage()) ? new Locale("el") : Locale.ENGLISH;
        String title = month.atDay(1).format(DateTimeFormatter.ofPattern("MMMM yyyy", locale));
        TextView label = centered(title, 20, ui.colors().primaryText(), true);
        row.addView(label, new LinearLayout.LayoutParams(0, -2, 2f));

        Button next = ui.smallButton(preferences.isRtl() ? "←" : "→", false);
        next.setEnabled(month.isBefore(MAX_MONTH));
        next.setOnClickListener(v -> host.navigate("calendar", month.plusMonths(1).toString()));
        row.addView(next, ui.weight(44));
        add(root, row, 10, 4);

        Button today = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_return_to_this_month_ea36d48b), false);
        today.setOnClickListener(v -> {
            YearMonth current = YearMonth.now();
            if (current.isBefore(MIN_MONTH)) current = MIN_MONTH;
            if (current.isAfter(MAX_MONTH)) current = MAX_MONTH;
            host.navigate("calendar", current.toString());
        });
        add(root, today, 0, 8);
    }

    private void addCalendarGrid(LinearLayout root) {
        GridLayout grid = new GridLayout(host.activity());
        grid.setColumnCount(7);
        grid.setAlignmentMode(GridLayout.ALIGN_BOUNDS);
        DayOfWeek[] weekdays = {DayOfWeek.SUNDAY, DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY};
        Locale locale = "ar".equals(preferences.effectiveLanguage()) ? new Locale("ar")
                : "el".equals(preferences.effectiveLanguage()) ? new Locale("el") : Locale.ENGLISH;
        for (DayOfWeek weekday : weekdays) {
            TextView head = centered(weekday.getDisplayName(TextStyle.SHORT, locale), 12, ThemePalette.GOLD, true);
            head.setBackground(ui.round(ThemePalette.NAVY, ThemePalette.GOLD, 8));
            grid.addView(head, cellParams());
        }

        LocalDate first = month.atDay(1);
        int leading = first.getDayOfWeek().getValue() % 7;
        for (int i = 0; i < leading; i++) grid.addView(new TextView(host.activity()), cellParams());
        Map<String, JSONObject> known = knownDays();
        for (int day = 1; day <= month.lengthOfMonth(); day++) {
            LocalDate date = month.atDay(day);
            String iso = date.toString();
            boolean current = iso.equals(data.currentAmmanDate());
            boolean hasDetails = known.containsKey(iso);
            String number = preferences.calendarMode().equals("julian")
                    ? day + "\n(" + julianLabel(date) + ")"
                    : Integer.toString(day);
            Button cell = ui.smallButton((hasDetails ? "• " : "") + number, current);
            cell.setMinHeight(ui.dp(48));
            cell.setContentDescription(iso + (hasDetails ? local(com.orthodoxprayers.privateapp.R.string.ui_details_available_c1c33f64) : ""));
            if (hasDetails) cell.setOnClickListener(v -> host.navigate("calendar_day", iso));
            grid.addView(cell, cellParams());
        }
        add(root, grid, 4, 12);
    }

    private GridLayout.LayoutParams cellParams() {
        GridLayout.LayoutParams params = new GridLayout.LayoutParams();
        params.width = 0;
        params.height = -2;
        params.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
        params.setMargins(ui.dp(2), ui.dp(2), ui.dp(2), ui.dp(2));
        params.setGravity(Gravity.FILL_HORIZONTAL);
        return params;
    }

    private void addKnownDays(LinearLayout root) {
        Map<String, JSONObject> known = knownDays();
        boolean any = false;
        for (Map.Entry<String, JSONObject> entry : known.entrySet()) {
            if (!YearMonth.from(LocalDate.parse(entry.getKey())).equals(month)) continue;
            if (!any) root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_trusted_details_this_month_a042797d)));
            any = true;
            JSONObject item = entry.getValue();
            LinearLayout card = ui.card();
            card.setClickable(true);
            card.setFocusable(true);
            card.setOnClickListener(v -> host.navigate("calendar_day", entry.getKey()));
            card.addView(ui.text(entry.getKey(), 16, ui.colors().primaryText(), true));
            String feast = localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), ""));
            String status = localized(item.optJSONObject("status"), localized(item.optJSONObject("fast"), ""));
            if (!status.isEmpty()) card.addView(ui.text(status, 13, ui.colors().accentText(), true));
            if (!feast.isEmpty()) card.addView(ui.text(feast, 13, ui.colors().secondaryText(), false));
            add(root, card, 2, 7);
        }
        if (!any) add(root, centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_published_details_for_this_month_are_included_9e8eb771), 14, ui.colors().secondaryText(), false), 10, 16);
    }

    private Map<String, JSONObject> knownDays() {
        Map<String, JSONObject> result = new HashMap<>();
        JSONArray annual = data.calendarDays(month.getYear());
        for (int i = 0; i < annual.length(); i++) {
            JSONObject item = annual.optJSONObject(i);
            if (item == null) continue;
            String date = item.optString("date_iso", item.optString("date", ""));
            if (!date.isEmpty()) result.put(date, item);
        }
        JSONArray weekly = data.rollingWeekDays();
        for (int i = 0; i < weekly.length(); i++) {
            JSONObject item = weekly.optJSONObject(i);
            if (item == null) continue;
            String date = item.optString("date_iso", "");
            if (!date.isEmpty()) result.put(date, item);
        }
        JSONObject today = data.today();
        if (!data.dataDate().isEmpty()) result.put(data.dataDate(), today);
        JSONArray upcoming = today.optJSONArray("upcoming");
        if (upcoming != null) {
            for (int i = 0; i < upcoming.length(); i++) {
                JSONObject item = upcoming.optJSONObject(i);
                if (item != null && !item.optString("date", "").isEmpty()) result.put(item.optString("date"), item);
            }
        }
        return result;
    }

    private static String julianLabel(LocalDate gregorian) {
        // For 1900–2099, old-calendar dates are 13 days behind the civil Gregorian date.
        LocalDate julian = gregorian.minusDays(13);
        return String.format(Locale.US, "%02d/%02d", julian.getDayOfMonth(), julian.getMonthValue());
    }
}
