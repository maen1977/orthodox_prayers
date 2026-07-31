package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class HomeScreen extends BaseScreen {
    // R14_HOME_COMPACT: duplicate home cards hidden; internal routes remain available.
    // R32_OWNER_UI_REFINEMENT: duplicate Sunday and utility cards are intentionally absent.
    public HomeScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(
                localized(data.library().optJSONObject("app_name"), local(com.orthodoxprayers.privateapp.R.string.ui_church_prayers_65a0f7e5)),
                false
        );
        addUpdateBanner(page.root);
        if (!data.hasDisplayableData()) {
            addEmptyState(page.root);
            addQuickAccess(page.root);
            return page.scroll;
        }
        addDateCard(page.root);
        addRollingWeekStatus(page.root);
        addQuickAccess(page.root);
        addUpcoming(page.root);
        return page.scroll;
    }

    private void addUpdateBanner(LinearLayout root) {
        if (data.isRefreshing() && !data.hasUsableCurrentData()) {
            add(root, ui.infoBadge(data.userFacingRefreshStatus()), 10, 2);
            return;
        }
        if (!data.hasUsableCurrentData()) {
            add(root, ui.badge(data.userFacingRefreshStatus(), false), 10, 2);
        }
    }

    private void addEmptyState(LinearLayout root) {
        LinearLayout card = ui.card();
        String title = data.isRefreshing()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_loading_today_s_data_8457881d)
                : local(com.orthodoxprayers.privateapp.R.string.ui_no_valid_daily_data_is_available_e60f7fe1);
        card.addView(centered(title, 19, ui.colors().primaryText(), true));
        String detail = data.isRefreshing()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_the_screen_will_update_automatically_after_downl_a93a7fcf)
                : local(com.orthodoxprayers.privateapp.R.string.ui_the_app_will_retry_automatically_you_can_also_re_d2cc490a);
        card.addView(centered(detail, 14, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 8, 0, 8));
        if (!data.isRefreshing()) {
            Button retry = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_retry_update_da94fa97), true);
            retry.setOnClickListener(v -> host.refreshData());
            card.addView(retry, ui.margins(-1, -2, 0, 6, 0, 0));
        }
        add(root, card, 12, 12);
    }

    private void addDateCard(LinearLayout root) {
        JSONObject today = data.today();
        LinearLayout card = ui.card();
        String dateValue = localized(today.optJSONObject("date_label"), data.dataDate());
        TextView date = centered(dateValue, 22, ui.colors().primaryText(), true);
        card.addView(date);

        String calendarValue = localized(today.optJSONObject("calendar_label"), "");
        if (!calendarValue.isEmpty()) {
            TextView calendar = centered(calendarValue, 14, ui.colors().secondaryText(), false);
            card.addView(calendar, ui.margins(-1, -2, 0, 4, 0, 0));
        }

        String fastingValue = fastingDisplayTitle(today, data.dataDate());
        TextView fast = centered(fastingValue, 18, ui.colors().accentText(), true);
        card.addView(fast, ui.margins(-1, -2, 0, 8, 0, 0));

        if (!data.isTodayCurrent()) {
            String staleText = localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_stale_trusted_copy_date_format,
                    data.dataDate()
            );
            card.addView(ui.badge(staleText, false), ui.margins(-1, -2, 0, 10, 0, 0));
        }
        add(root, card, 12, 10);
    }

    private void addRollingWeekStatus(LinearLayout root) {
        LinearLayout card = ui.card();
        boolean ready = data.hasCompleteRollingWeek();
        String end = data.rollingWeekEndDate();
        String title = ready
                ? local(com.orthodoxprayers.privateapp.R.string.ui_nine_day_service_ready)
                : local(com.orthodoxprayers.privateapp.R.string.ui_the_complete_weekly_package_is_not_available_yet_e438506f);
        card.addView(centered(title, 16,
                ready ? ui.colors().accentText() : ui.colors().secondaryText(), true));
        if (ready && !end.isEmpty()) {
            card.addView(centered(localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_content_ready_through_format,
                    end
            ), 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 5, 0, 0));
        }
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(v -> host.navigate("upcoming", null));
        add(root, card, 0, 10);
    }

    private void addQuickAccess(LinearLayout root) {
        root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_quick_access_c927e8a2)));
        Button liturgy = ui.iconButton(
                com.orthodoxprayers.privateapp.R.drawable.ic_action_liturgy,
                todayLiturgyButtonLabel(),
                true
        );
        liturgy.setTextSize(17 * preferences.fontScale());
        liturgy.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
        add(root, liturgy, 2, 8);

        LinearLayout first = ui.row();
        addShortcut(first, com.orthodoxprayers.privateapp.R.drawable.ic_action_readings, local(com.orthodoxprayers.privateapp.R.string.ui_daily_readings_7f88fcc0), "readings", null);
        addShortcut(first, com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers, local(com.orthodoxprayers.privateapp.R.string.ui_daily_prayers_ef97d9fd), "prayers", null);
        add(root, first, 0, 0);

        LinearLayout second = ui.row();
        addShortcut(second, com.orthodoxprayers.privateapp.R.drawable.ic_action_calendar, local(com.orthodoxprayers.privateapp.R.string.ui_calendar_and_fasting_51a9bf84), "calendar", null);
        addShortcut(second, com.orthodoxprayers.privateapp.R.drawable.ic_action_live, local(com.orthodoxprayers.privateapp.R.string.ui_churches_and_live_services_53a37eff), "churches", null);
        add(root, second, 0, 10);
    }

    private void addShortcut(LinearLayout row, int iconResource, String title, String screen, String argument) {
        Button button = ui.iconButton(iconResource, title, false);
        button.setOnClickListener(v -> host.navigate(screen, argument));
        row.addView(button, ui.weight(76));
    }

    private void addUpcoming(LinearLayout root) {
        JSONArray upcoming = data.today().optJSONArray("upcoming");
        if (upcoming == null || upcoming.length() == 0) return;

        LinearLayout table = ui.card();

        LinearLayout header = ui.row();
        header.setPadding(ui.dp(8), ui.dp(4), ui.dp(8), ui.dp(6));
        TextView dayHeader = ui.text(
                local(com.orthodoxprayers.privateapp.R.string.ui_day_and_commemoration_ab4b3d7f),
                13,
                ui.colors().primaryText(),
                true
        );
        TextView fastingHeader = ui.text(
                local(com.orthodoxprayers.privateapp.R.string.ui_fasting_f1b1605d),
                13,
                ui.colors().accentText(),
                true
        );
        fastingHeader.setGravity(android.view.Gravity.CENTER);
        header.addView(dayHeader, new LinearLayout.LayoutParams(0, -2, 2f));
        header.addView(fastingHeader, new LinearLayout.LayoutParams(0, -2, 1f));
        table.addView(header);

        int dayCount = Math.min(8, upcoming.length());
        for (int i = 0; i < dayCount; i++) {
            JSONObject item = upcoming.optJSONObject(i);
            if (item == null) continue;
            String date = item.optString("date", "");
            String day = localized(item.optJSONObject("day"), date);
            String feast = displayableCommemoration(item);
            JSONObject selection = item.optJSONObject("liturgy_service_selection");
            String liturgy = selection == null ? "" : localized(selection.optJSONObject("label"), "");
            String status = fastingDisplayTitle(item, date);

            LinearLayout row = ui.row();
            row.setPadding(ui.dp(8), ui.dp(7), ui.dp(8), ui.dp(7));
            row.setClickable(!date.isEmpty());
            row.setFocusable(!date.isEmpty());
            String dayAndFeast = day
                    + (feast.isEmpty() ? "" : "\n" + feast)
                    + (liturgy.isEmpty() ? "" : "\n" + liturgy);
            TextView dayView = ui.text(dayAndFeast, 13, ui.colors().secondaryText(), false);
            dayView.setMaxLines(3);
            TextView statusView = ui.text(status, 13, ui.colors().accentText(), true);
            statusView.setGravity(android.view.Gravity.CENTER);
            statusView.setMaxLines(3);
            row.addView(dayView, new LinearLayout.LayoutParams(0, -2, 2f));
            row.addView(statusView, new LinearLayout.LayoutParams(0, -2, 1f));
            row.setContentDescription(day + ". " + status + (feast.isEmpty() ? "" : ". " + feast));
            if (!date.isEmpty()) {
                row.setOnClickListener(v -> host.navigate("calendar_day", date));
            }
            table.addView(row);

            if (i + 1 < dayCount) {
                View divider = new View(host.activity());
                divider.setBackgroundColor(ui.colors().secondaryText());
                divider.setAlpha(0.16f);
                table.addView(divider, new LinearLayout.LayoutParams(-1, ui.dp(1)));
            }
        }
        add(root, table, 0, 12);
    }

    private String todayLiturgyButtonLabel() {
        JSONObject selection = data.today().optJSONObject("liturgy_service_selection");
        String selected = selection == null ? "" : localized(selection.optJSONObject("label"), "");
        if (selected.isEmpty()) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_full_liturgy_today_preparation_to_dismissal_08927fc7);
        }
        return localFormat(
                com.orthodoxprayers.privateapp.R.string.ui_open_full_appointed_liturgy_format,
                selected
        );
    }


}
