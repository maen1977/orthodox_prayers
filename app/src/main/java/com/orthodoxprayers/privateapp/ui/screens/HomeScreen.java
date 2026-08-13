package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.data.FastingNoticeEngine;
import com.orthodoxprayers.privateapp.data.PrayerOfDaySelector;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.time.DayOfWeek;
import java.time.LocalDate;
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
        addSmartFastingNotice(page.root);
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
        String dateValue = civilDateLabel(today);
        TextView date = centered(dateValue, 22, ui.colors().primaryText(), true);
        card.addView(date);

        String oldCalendarDate = oldCalendarDateLabel(today);
        if (!oldCalendarDate.isEmpty()) {
            String calendarValue = localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_old_church_calendar_home_format,
                    oldCalendarDate
            );
            TextView calendar = centered(calendarValue, 15, ui.colors().secondaryText(), true);
            card.addView(calendar, ui.margins(-1, -2, 0, 5, 0, 0));
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

        LinearLayout third = ui.row();
        addShortcutCard(third, com.orthodoxprayers.privateapp.R.drawable.ic_action_readings, bibleTitle(), "bible", null);
        addShortcutCard(third, com.orthodoxprayers.privateapp.R.drawable.ic_action_search, searchTitle(), "search", null);
        add(root, third, 0, 6);
    }

    private LinearLayout addShortcutCard(LinearLayout row, int iconResource, String title, String screen, String argument) {
        LinearLayout card = ui.shortcutCard(iconResource, title);
        card.setOnClickListener(v -> host.navigate(screen, argument));
        row.addView(card, ui.weight(96));
        return card;
    }

    private String bibleTitle() {
        String language = preferences.effectiveLanguage();
        if ("ar".equals(language)) return "الكتاب المقدس";
        if ("el".equals(language)) return "Ἁγία Γραφή";
        return "Holy Bible";
    }

    private String searchTitle() {
        String language = preferences.effectiveLanguage();
        if ("ar".equals(language)) return "البحث";
        if ("el".equals(language)) return "Ἀναζήτηση";
        return "Search";
    }

    private void addSmartFastingNotice(LinearLayout root) {
        LocalDate baseDate = currentDataDate();
        FastingNoticeEngine.Notice notice = FastingNoticeEngine.evaluate(
                baseDate,
                isoDate -> data.calendarDay(isoDate)
        );
        String title = fastingNoticeTitle(notice);
        LinearLayout card = ui.actionCard(
                com.orthodoxprayers.privateapp.R.drawable.ic_action_calendar,
                title,
                local(com.orthodoxprayers.privateapp.R.string.ui_fast_notice_details_hint)
        );
        card.setElevation(ui.dp(9));
        card.setTranslationZ(ui.dp(2));
        card.setOnClickListener(v -> {
            if (notice.kind == FastingNoticeEngine.Kind.NONE || notice.targetDate == null) {
                host.navigate("upcoming", null);
            } else {
                host.navigate("fasting_summary", notice.targetDate.toString());
            }
        });
        add(root, card, 4, 12);
    }

    private String fastingNoticeTitle(FastingNoticeEngine.Notice notice) {
        if (notice == null) return local(com.orthodoxprayers.privateapp.R.string.ui_fast_notice_none);
        if (notice.kind == FastingNoticeEngine.Kind.CURRENT_MAJOR_FAST) {
            String family = fastFamilyTitle(notice.family);
            if (notice.dayNumber == 1) {
                return localFormat(
                        com.orthodoxprayers.privateapp.R.string.ui_fast_notice_first_day_format,
                        family
                );
            }
            if (notice.daysRemaining <= 0) {
                return localFormat(
                        com.orthodoxprayers.privateapp.R.string.ui_fast_notice_last_day_format,
                        family
                );
            }
            if (notice.daysRemaining <= 3) {
                if (notice.daysRemaining == 1) {
                    return localFormat(
                            com.orthodoxprayers.privateapp.R.string.ui_fast_notice_ends_in_one_day_format,
                            family
                    );
                }
                if (notice.daysRemaining == 2) {
                    return localFormat(
                            com.orthodoxprayers.privateapp.R.string.ui_fast_notice_ends_in_two_days_format,
                            family
                    );
                }
                return localFormat(
                        com.orthodoxprayers.privateapp.R.string.ui_fast_notice_ends_in_days_format,
                        notice.daysRemaining,
                        family
                );
            }
            return localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_fast_notice_current_format,
                    notice.dayNumber,
                    family
            );
        }
        if (notice.kind == FastingNoticeEngine.Kind.UPCOMING_MAJOR_FAST) {
            String family = fastFamilyTitle(notice.family);
            if (notice.daysUntilStart == 1) {
                return localFormat(
                        com.orthodoxprayers.privateapp.R.string.ui_fast_notice_starts_tomorrow_format,
                        family
                );
            }
            return localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_fast_notice_starts_in_days_format,
                    notice.daysUntilStart,
                    family
            );
        }
        if (notice.kind == FastingNoticeEngine.Kind.UPCOMING_WEEKLY_FAST) {
            String weekday = weekdayTitle(notice.weekday);
            String fastTitle = notice.weekday == DayOfWeek.WEDNESDAY
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_wednesday_fast)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_friday_fast);
            if (notice.daysUntilStart == 1) {
                return localFormat(
                        com.orthodoxprayers.privateapp.R.string.ui_fast_notice_tomorrow_weekly_format,
                        weekday,
                        fastTitle
                );
            }
            return localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_fast_notice_next_weekly_format,
                    weekday,
                    fastTitle
            );
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_fast_notice_none);
    }

    private String fastFamilyTitle(FastingNoticeEngine.Family family) {
        if (family == FastingNoticeEngine.Family.DORMITION) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_fast_family_dormition);
        }
        if (family == FastingNoticeEngine.Family.NATIVITY) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_fast_family_nativity);
        }
        if (family == FastingNoticeEngine.Family.GREAT_LENT) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_fast_family_great_lent);
        }
        if (family == FastingNoticeEngine.Family.APOSTLES) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_fast_family_apostles);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_no_fast_plain);
    }

    private String weekdayTitle(DayOfWeek weekday) {
        if (weekday == DayOfWeek.WEDNESDAY) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_weekday_wednesday);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_weekday_friday);
    }

    private LocalDate currentDataDate() {
        String value = data.today().optString("date_iso", data.dataDate()).trim();
        try { return LocalDate.parse(value); }
        catch (Exception ignored) { return ZonedDateTime.now(AMMAN_ZONE).toLocalDate(); }
    }

    private String civilDateLabel(JSONObject today) {
        String value = localized(today.optJSONObject("date_label"), data.dataDate()).trim();
        int legacySeparator = value.indexOf(" / ");
        if (legacySeparator > 0) value = value.substring(0, legacySeparator).trim();
        return value.isEmpty() ? data.dataDate() : value;
    }

    private String oldCalendarDateLabel(JSONObject today) {
        String localizedLabel = localized(today.optJSONObject("julian_label"), "").trim();
        if (!localizedLabel.isEmpty()) return localizedLabel;
        Object raw = today.opt("julian_date");
        if (raw instanceof JSONObject) {
            JSONObject object = (JSONObject) raw;
            String objectLabel = localized(object, "").trim();
            if (!objectLabel.isEmpty()) return objectLabel;
            String legacyArabicLabel = object.optString("label_ar", "").trim();
            if (!legacyArabicLabel.isEmpty() && "ar".equals(preferences.effectiveLanguage())) {
                return legacyArabicLabel;
            }
        }
        String iso = raw == null ? "" : String.valueOf(raw).trim();
        return iso;
    }

    private String currentPrayerServiceId() {
        return PrayerOfDaySelector.forTime(ZonedDateTime.now(AMMAN_ZONE).toLocalTime());
    }




}
