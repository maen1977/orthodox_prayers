package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.time.DayOfWeek;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

public final class HomeScreen extends BaseScreen {
    // R14_HOME_COMPACT: duplicate home cards hidden; internal routes remain available.
    // R32_OWNER_UI_REFINEMENT: duplicate Sunday and utility cards are intentionally absent.
    // R33_COMPACT_FASTING_HOME: the multi-day fasting table lives behind the calendar icon.
    // R35_HOME_SHORTCUT_CARDS: four compact shortcuts plus one context-aware recommendation.
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
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
        addQuickAccess(page.root);
        addSmartRecommendation(page.root);
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

        LinearLayout first = ui.row();
        String prayerOfTheDay = local(com.orthodoxprayers.privateapp.R.string.ui_prayer_of_the_day);
        LinearLayout prayerCard = addShortcutCard(
                first,
                com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers,
                prayerOfTheDay,
                "reader",
                currentPrayerServiceId()
        );
        prayerCard.setContentDescription(
                prayerOfTheDay + ". " + local(com.orthodoxprayers.privateapp.R.string.ui_daily_prayers_ef97d9fd)
        );
        addShortcutCard(first, com.orthodoxprayers.privateapp.R.drawable.ic_action_readings, local(com.orthodoxprayers.privateapp.R.string.ui_daily_readings_7f88fcc0), "readings", null);
        add(root, first, 0, 0);

        LinearLayout second = ui.row();
        addShortcutCard(second, com.orthodoxprayers.privateapp.R.drawable.ic_action_calendar, local(com.orthodoxprayers.privateapp.R.string.ui_calendar_and_fasting_51a9bf84), "upcoming", null);
        addShortcutCard(second, com.orthodoxprayers.privateapp.R.drawable.ic_action_live, local(com.orthodoxprayers.privateapp.R.string.ui_churches_and_live_services_53a37eff), "churches", null);
        add(root, second, 0, 6);
    }

    private LinearLayout addShortcutCard(LinearLayout row, int iconResource, String title, String screen, String argument) {
        LinearLayout card = ui.shortcutCard(iconResource, title);
        card.setOnClickListener(v -> host.navigate(screen, argument));
        row.addView(card, ui.weight(96));
        return card;
    }

    private void addSmartRecommendation(LinearLayout root) {
        SmartShortcut recommendation = smartRecommendation();
        LinearLayout card = ui.actionCard(recommendation.iconResource, recommendation.title, recommendation.subtitle);
        if ("reader".equals(recommendation.screen) && "divine_liturgy".equals(recommendation.argument)) {
            card.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
        } else {
            card.setOnClickListener(v -> host.navigate(recommendation.screen, recommendation.argument));
        }
        add(root, card, 2, 10);
    }

    private SmartShortcut smartRecommendation() {
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        JSONObject today = data.today();
        String specificCommemoration = specificCommemoration(today);
        if (!specificCommemoration.isEmpty()) {
            return new SmartShortcut(
                    com.orthodoxprayers.privateapp.R.drawable.ic_action_liturgy,
                    specificCommemoration,
                    todayLiturgyButtonLabel(),
                    "reader",
                    "divine_liturgy"
            );
        }
        if (now.getDayOfWeek() == DayOfWeek.SUNDAY) {
            return serviceShortcut("pre_communion_prayers", "prayer_category", "communion");
        }
        LocalTime time = now.toLocalTime();
        if (time.isBefore(LocalTime.of(7, 0))) {
            return serviceShortcut("pre_communion_prayers", "reader", "pre_communion_prayers");
        }
        if (time.isBefore(LocalTime.of(12, 0))) {
            return serviceShortcut("morning_prayer", "reader", "morning_prayer");
        }
        if (!time.isBefore(LocalTime.of(18, 0))) {
            return serviceShortcut("small_compline", "reader", "small_compline");
        }
        String subtitle = data.hasCompleteRollingWeek() && !data.rollingWeekEndDate().isEmpty()
                ? localFormat(com.orthodoxprayers.privateapp.R.string.ui_content_ready_through_format, data.rollingWeekEndDate())
                : local(com.orthodoxprayers.privateapp.R.string.ui_the_complete_weekly_package_is_not_available_yet_e438506f);
        return new SmartShortcut(
                com.orthodoxprayers.privateapp.R.drawable.ic_action_calendar,
                local(com.orthodoxprayers.privateapp.R.string.ui_nine_day_service_ready),
                subtitle,
                "upcoming",
                null
        );
    }

    private SmartShortcut serviceShortcut(String serviceId, String screen, String argument) {
        JSONObject service = data.findService(serviceId);
        String title = service == null
                ? local(com.orthodoxprayers.privateapp.R.string.ui_prayer_48a8929a)
                : localized(service.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_prayer_48a8929a));
        String subtitle = service == null ? "" : localized(service.optJSONObject("summary"), "");
        return new SmartShortcut(
                "pre_communion_prayers".equals(serviceId)
                        ? com.orthodoxprayers.privateapp.R.drawable.ic_action_liturgy
                        : com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers,
                title,
                subtitle,
                screen,
                argument
        );
    }

    private String currentPrayerServiceId() {
        LocalTime time = ZonedDateTime.now(AMMAN_ZONE).toLocalTime();
        if (time.isBefore(LocalTime.of(12, 0))) return "morning_prayer";
        if (!time.isBefore(LocalTime.of(18, 0))) return "evening_prayer";
        return "thanksgiving";
    }

    private String specificCommemoration(JSONObject today) {
        if (today == null) return "";
        JSONObject localCommemoration = today.optJSONObject("local_commemoration");
        if (localCommemoration != null) {
            String title = localized(localCommemoration.optJSONObject("title"), "");
            if (!title.isEmpty()) return title;
        }
        JSONObject commemoration = today.optJSONObject("commemoration");
        return commemoration == null ? "" : localized(commemoration.optJSONObject("title"), "");
    }

    private static final class SmartShortcut {
        final int iconResource;
        final String title;
        final String subtitle;
        final String screen;
        final String argument;

        SmartShortcut(int iconResource, String title, String subtitle, String screen, String argument) {
            this.iconResource = iconResource;
            this.title = title;
            this.subtitle = subtitle;
            this.screen = screen;
            this.argument = argument;
        }
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
