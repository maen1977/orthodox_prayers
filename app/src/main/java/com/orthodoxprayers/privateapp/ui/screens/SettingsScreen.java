package com.orthodoxprayers.privateapp.ui.screens;

import android.Manifest;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.os.Build;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.TimePicker;

import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.ui.LocalePolicy;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.time.ZoneId;
import java.util.Locale;

public final class SettingsScreen extends BaseScreen {
    public SettingsScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_settings_25169a1d), true);
        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_app_and_text_language_10b5a3ac)));
        LinearLayout languages = ui.row();
        addLanguageButton(languages, local(com.orthodoxprayers.privateapp.R.string.ui_language_arabic_name), "ar");
        addLanguageButton(languages, local(com.orthodoxprayers.privateapp.R.string.ui_language_english_name), "en");
        addLanguageButton(languages, local(com.orthodoxprayers.privateapp.R.string.ui_language_greek_name), "el");
        add(page.root, languages, 0, 5);

        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_reading_0443f4e6)));
        LinearLayout font = ui.row();
        Button smaller = ui.button("A−", false);
        smaller.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_decrease_text_size_d4631a2b));
        smaller.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() - 0.1f); host.navigate("settings", null); });
        font.addView(smaller, ui.weight(48));
        Button reset = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_default_25612288), false);
        reset.setOnClickListener(v -> { preferences.setFontScale(1.0f); host.navigate("settings", null); });
        font.addView(reset, ui.weight(48));
        Button larger = ui.button("A+", false);
        larger.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_increase_text_size_d8c66ed2));
        larger.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() + 0.1f); host.navigate("settings", null); });
        font.addView(larger, ui.weight(48));
        add(page.root, font, 0, 5);

        Button dark = ui.button(preferences.darkMode()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_use_light_mode_1c895a15)
                : local(com.orthodoxprayers.privateapp.R.string.ui_use_dark_mode_1564a2ea), preferences.darkMode());
        dark.setOnClickListener(v -> { preferences.setDarkMode(!preferences.darkMode()); host.navigate("settings", null); });
        add(page.root, dark, 0, 6);

        Button keepOn = ui.button(preferences.keepScreenOn()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_disable_keep_screen_on_14c0033c)
                : local(com.orthodoxprayers.privateapp.R.string.ui_keep_screen_on_while_reading_f9d35a52), preferences.keepScreenOn());
        keepOn.setOnClickListener(v -> { preferences.setKeepScreenOn(!preferences.keepScreenOn()); host.navigate("settings", null); });
        add(page.root, keepOn, 0, 6);

        LinearLayout spacing = ui.row();
        Button tighter = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_less_spacing_182a14c2), false);
        tighter.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(preferences.lineSpacingMultiplier() - 0.1f); host.navigate("settings", null); });
        spacing.addView(tighter, ui.weight(48));
        Button spacingReset = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_spacing_385760af) + String.format(Locale.US, "%.2f", preferences.lineSpacingMultiplier()), false);
        spacingReset.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(1.16f); host.navigate("settings", null); });
        spacing.addView(spacingReset, ui.weight(48));
        Button wider = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_more_spacing_fe47f0f9), false);
        wider.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(preferences.lineSpacingMultiplier() + 0.1f); host.navigate("settings", null); });
        spacing.addView(wider, ui.weight(48));
        add(page.root, spacing, 0, 5);

        Button fontFamily = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_font_f5e02ef6) + fontFamilyLabel(), false);
        fontFamily.setOnClickListener(v -> {
            String current = preferences.fontFamily();
            preferences.setFontFamily("sans".equals(current) ? "serif" : "serif".equals(current) ? "monospace" : "sans");
            host.navigate("settings", null);
        });
        add(page.root, fontFamily, 0, 6);

        Button autoScroll = ui.button(autoScrollSettingLabel(), preferences.autoScrollSpeed() > 0);
        autoScroll.setOnClickListener(v -> {
            int speed = preferences.autoScrollSpeed();
            preferences.setAutoScrollSpeed(speed >= 4 ? 0 : speed + 1);
            host.navigate("settings", null);
        });
        add(page.root, autoScroll, 0, 10);

        LinearLayout readerAppearance = ui.row();
        Button readerTheme = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_reader_theme_70f179d4) + readerThemeLabel(), false);
        readerTheme.setOnClickListener(v -> {
            String current = preferences.readerTheme();
            preferences.setReaderTheme("system".equals(current) ? "sepia" : "sepia".equals(current) ? "night" : "system");
            host.navigate("settings", null);
        });
        readerAppearance.addView(readerTheme, new LinearLayout.LayoutParams(0, -2, 2f));
        Button brightness = ui.smallIconButton(com.orthodoxprayers.privateapp.R.drawable.ic_action_brightness,
                preferences.readerBrightnessPercent() + "%", false);
        brightness.setOnClickListener(v -> {
            int current = preferences.readerBrightnessPercent();
            preferences.setReaderBrightnessPercent(current > 80 ? 80 : current > 60 ? 60 : current > 40 ? 40 : current > 20 ? 20 : 100);
            host.navigate("settings", null);
        });
        readerAppearance.addView(brightness, ui.weight(48));
        add(page.root, readerAppearance, 0, 6);

        Button resetReading = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_reset_reading_settings_71533aa3), false);
        resetReading.setOnClickListener(v -> new AlertDialog.Builder(host.activity())
                .setTitle(local(com.orthodoxprayers.privateapp.R.string.ui_reset_reading_settings_34ebb828))
                .setMessage(local(com.orthodoxprayers.privateapp.R.string.ui_text_size_font_spacing_reader_theme_brightness_a_5b5d5d0b))
                .setPositiveButton(local(com.orthodoxprayers.privateapp.R.string.ui_reset_7b5a50be), (dialog, which) -> {
                    preferences.resetReaderPreferences();
                    host.navigate("settings", null);
                })
                .setNegativeButton(local(com.orthodoxprayers.privateapp.R.string.ui_cancel_1bd7a4b9), null)
                .show());
        add(page.root, resetReading, 0, 10);

        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_calendar_and_reminders_acba78af)));
        LinearLayout quietHours = ui.row();
        Button quietStart = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_quiet_starts_91bc6653) + formatMinute(preferences.quietHoursStartMinute()), false);
        quietStart.setOnClickListener(v -> showTimePicker(preferences.quietHoursStartMinute(), minute -> {
            preferences.setQuietHours(minute, preferences.quietHoursEndMinute());
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
        }));
        quietHours.addView(quietStart, ui.weight(60));
        Button quietEnd = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_quiet_ends_f728171c) + formatMinute(preferences.quietHoursEndMinute()), false);
        quietEnd.setOnClickListener(v -> showTimePicker(preferences.quietHoursEndMinute(), minute -> {
            preferences.setQuietHours(preferences.quietHoursStartMinute(), minute);
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
        }));
        quietHours.addView(quietEnd, ui.weight(60));
        add(page.root, quietHours, 0, 6);
        TextView quietNotice = centered(local(com.orthodoxprayers.privateapp.R.string.ui_the_app_will_not_notify_during_the_selected_quie_1f2f6d07), 12, ui.colors().secondaryText(), false);
        add(page.root, quietNotice, 0, 8);

        Button calendarMode = ui.button("julian".equals(preferences.calendarMode())
                ? local(com.orthodoxprayers.privateapp.R.string.ui_show_gregorian_dates_only_f6e30c65)
                : local(com.orthodoxprayers.privateapp.R.string.ui_show_julian_dates_beside_gregorian_12fda2c8), "julian".equals(preferences.calendarMode()));
        calendarMode.setOnClickListener(v -> {
            preferences.setCalendarMode("julian".equals(preferences.calendarMode()) ? "gregorian" : "julian");
            host.navigate("settings", null);
        });
        add(page.root, calendarMode, 0, 6);

        addReminder(page.root, ReminderScheduler.MORNING, local(com.orthodoxprayers.privateapp.R.string.ui_morning_prayer_a517a36b), 6 * 60 + 30);
        addReminder(page.root, ReminderScheduler.READING, local(com.orthodoxprayers.privateapp.R.string.ui_daily_readings_295eb6f5), 8 * 60);
        addReminder(page.root, ReminderScheduler.EVENING, local(com.orthodoxprayers.privateapp.R.string.ui_evening_prayer_50c26316), 21 * 60);
        addReminder(page.root, ReminderScheduler.FEAST, local(com.orthodoxprayers.privateapp.R.string.ui_feasts_and_commemorations_bea321c8), 7 * 60);
        addReminder(page.root, ReminderScheduler.FAST, local(com.orthodoxprayers.privateapp.R.string.ui_fasting_status_7fa7fda1), 7 * 60 + 15);
        addReminder(page.root, ReminderScheduler.PERSONAL, local(com.orthodoxprayers.privateapp.R.string.ui_personal_reminder_b0bd49be), 18 * 60);

        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_update_and_data_bf22bb6d)));
        Button refresh = ui.button(
                data.isRefreshing()
                        ? local(com.orthodoxprayers.privateapp.R.string.ui_update_in_progress_7d1054d7)
                        : local(com.orthodoxprayers.privateapp.R.string.ui_refresh_today_s_data_now_98188698),
                data.isRefreshing()
        );
        refresh.setEnabled(!data.isRefreshing());
        refresh.setOnClickListener(v -> host.refreshData());
        add(page.root, refresh, 0, 7);

        TextView automaticUpdateNotice = ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_the_app_performs_two_verified_checks_each_day_01_8fac151b));
        add(page.root, automaticUpdateNotice, 0, 8);

        String lastUpdate = formatTimestamp(preferences.lastSuccessfulUpdate(),
                local(com.orthodoxprayers.privateapp.R.string.ui_no_successful_network_update_yet_12387d86));
        String lastAttempt = formatTimestamp(preferences.lastRefreshAttempt(),
                local(com.orthodoxprayers.privateapp.R.string.ui_no_attempt_has_been_made_yet_478bda45));
        String dateValue = data.dataDate().isEmpty()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_unavailable_24f3ca2e)
                : data.dataDate();
        TextView updateState = data.isRefreshing()
                ? ui.infoBadge(data.userFacingRefreshStatus())
                : ui.badge(data.userFacingRefreshStatus(), preferences.lastRefreshSucceeded() && data.isTodayCurrent());
        add(page.root, updateState, 0, 8);

        TextView summary = centered(local(com.orthodoxprayers.privateapp.R.string.ui_app_version_cf5bb661) + BuildConfig.VERSION_NAME
                + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_displayed_data_date_3ac6be9b) + dateValue
                + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_services_complete_through_df2f69fc)
                + (data.rollingWeekEndDate().isEmpty() ? local(com.orthodoxprayers.privateapp.R.string.ui_unavailable_24f3ca2e) : data.rollingWeekEndDate())
                + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_last_successful_check_dabe14f5) + lastUpdate,
                13, ui.colors().secondaryText(), false);
        add(page.root, summary, 0, 6);

        Button diagnosticsToggle = ui.button(preferences.advancedDiagnosticsExpanded()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_technical_details_800e4b8e)
                : local(com.orthodoxprayers.privateapp.R.string.ui_show_technical_details_97bf206d),
                preferences.advancedDiagnosticsExpanded());
        diagnosticsToggle.setOnClickListener(v -> {
            preferences.setAdvancedDiagnosticsExpanded(!preferences.advancedDiagnosticsExpanded());
            host.navigate("settings", null);
        });
        add(page.root, diagnosticsToggle, 0, 6);

        if (preferences.advancedDiagnosticsExpanded()) {
            TextView status = centered(local(com.orthodoxprayers.privateapp.R.string.ui_last_update_attempt_b3ee7523) + lastAttempt
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_update_diagnostic_code_400000df) + LocalePolicy.isolateTechnical(data.refreshDiagnosticCode())
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_update_manifest_revision_985fb3a6) + preferences.acceptedManifestRevisionForDate(data.dataDate())
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_trusted_copy_source_4596d692) + trustSourceLabel()
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_content_fingerprint_8e9ffe73) + LocalePolicy.isolateTechnical(shortHash(data.contentHash()))
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_scripture_source_id_b0a300e5) + LocalePolicy.isolateTechnical(safeValue(data.canonicalSourceId()))
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_selected_official_source_5cf4ee01) + officialSourceLabel(data.selectedOfficialSource())
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_automatic_update_01_00_and_06_00_amman_time_plus_a1bb2912)
                    + "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_verification_https_independent_digital_signature_a5a78dda),
                    13, ui.colors().secondaryText(), false);
            status.setTextIsSelectable(true);
            add(page.root, status, 0, 8);
            page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_sources_and_references_1a2c2926)));
            int registeredSourceCount = data.registeredSources().length();
            TextView sourceRegistryNotice = ui.infoBadge(localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_registered_sources_count_format,
                    registeredSourceCount
            ));
            add(page.root, sourceRegistryNotice, 0, 7);
            JSONObject healthSummary = data.sourceHealth().optJSONObject("summary");
            if (healthSummary != null) {
                TextView health = ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_source_monitor_d991048b)
                                + healthSummary.optInt("usable_connector_count", 0) + "/" + healthSummary.optInt("connector_count", 0),
                        healthSummary.optInt("usable_connector_count", 0) > 0);
                add(page.root, health, 0, 6);
            }
            Button sources = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_view_all_sources_1b4296c4), false);
            sources.setOnClickListener(v -> host.navigate("sources", null));
            add(page.root, sources, 0, 10);

            String sourceNote = data.sourceNote();
            if (!sourceNote.isEmpty()) {
                TextView source = centered(local(com.orthodoxprayers.privateapp.R.string.ui_about_the_content_source_8d523461) + sourceNote,
                        13, ui.colors().secondaryText(), false);
                add(page.root, source, 0, 8);
            }
        }

        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_live_services_dc308682)));
        Button churches = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_church_directory_and_live_services_b4f52ad3), false);
        churches.setOnClickListener(v -> host.navigate("churches", null));
        add(page.root, churches, 0, 10);
        // R14_SETTINGS_CLEANUP: keep the free-app notice but hide call/privacy actions.
        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_about_the_app_3bd794db)));
        LinearLayout aboutCard = ui.card();
        TextView freeNotice = centered(local(com.orthodoxprayers.privateapp.R.string.ui_this_application_is_free_and_is_presented_by_mae_55914117), 15, ui.colors().primaryText(), true);
        freeNotice.setTextIsSelectable(true);
        aboutCard.addView(freeNotice);
        add(page.root, aboutCard, 0, 10);

        TextView privacy = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_ads_login_or_tracking_no_private_keys_are_sto_428b410a), 13, ui.colors().secondaryText(), false);
        add(page.root, privacy, 0, 16);
        return page.scroll;
    }

    private void addReminder(LinearLayout root, String kind, String label, int fallbackMinute) {
        LinearLayout row = ui.row();
        boolean enabled = preferences.remindersEnabled(kind);
        Button toggle = ui.button(label, enabled);
        toggle.setOnClickListener(v -> {
            boolean next = !preferences.remindersEnabled(kind);
            if (next && Build.VERSION.SDK_INT >= 33
                    && host.activity().checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                preferences.setPendingReminderKind(kind);
                host.activity().requestPermissions(
                        new String[]{Manifest.permission.POST_NOTIFICATIONS},
                        ReminderScheduler.NOTIFICATION_PERMISSION_REQUEST
                );
                return;
            }
            preferences.setRemindersEnabled(kind, next);
            ReminderScheduler scheduler = new ReminderScheduler(host.activity(), preferences);
            if (next) scheduler.schedule(kind); else scheduler.cancel(kind);
            host.navigate("settings", null);
        });
        row.addView(toggle, new LinearLayout.LayoutParams(0, -2, 2f));

        int minute = preferences.reminderMinuteOfDay(kind, fallbackMinute);
        Button time = ui.button(formatMinute(minute), false);
        time.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_change_time_for_9b3639ec) + label);
        time.setOnClickListener(v -> showTimePicker(preferences.reminderMinuteOfDay(kind, fallbackMinute), selectedMinute -> {
            preferences.setReminderMinuteOfDay(kind, selectedMinute);
            if (preferences.remindersEnabled(kind)) new ReminderScheduler(host.activity(), preferences).schedule(kind);
        }));
        row.addView(time, ui.weight(48));
        add(root, row, 0, 5);
    }

    private String autoScrollSettingLabel() {
        int speed = preferences.autoScrollSpeed();
        return speed == 0
                ? local(com.orthodoxprayers.privateapp.R.string.ui_auto_scroll_off_763228b7)
                : local(com.orthodoxprayers.privateapp.R.string.ui_auto_scroll_speed_9b395f14) + speed;
    }

    private String readerThemeLabel() {
        String theme = preferences.readerTheme();
        if ("sepia".equals(theme)) return local(com.orthodoxprayers.privateapp.R.string.ui_sepia_eea06eb6);
        if ("night".equals(theme)) return local(com.orthodoxprayers.privateapp.R.string.ui_night_e4245684);
        return local(com.orthodoxprayers.privateapp.R.string.ui_system_30211fca);
    }

    private String fontFamilyLabel() {
        if ("serif".equals(preferences.fontFamily())) return local(com.orthodoxprayers.privateapp.R.string.ui_serif_f8812e5c);
        if ("monospace".equals(preferences.fontFamily())) return local(com.orthodoxprayers.privateapp.R.string.ui_monospace_420f56d9);
        return local(com.orthodoxprayers.privateapp.R.string.ui_sans_ed854c03);
    }

    private String formatMinute(int minuteOfDay) {
        return LocalePolicy.formatClock(minuteOfDay, preferences.effectiveLanguage());
    }

    private String trustSourceLabel() {
        String source = data.trustSource();
        if ("signed_remote".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_signed_network_update_b1b4e0f9);
        if ("signed_cache".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_signed_local_copy_aee2c1da);
        if ("signed_backup".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_last_trusted_backup_50f6c814);
        if ("signed_embedded".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_signed_embedded_copy_17eb1066);
        return local(com.orthodoxprayers.privateapp.R.string.ui_unknown_13adce42);
    }

    private String officialSourceLabel(String source) {
        if ("orthodox_jordan".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_orthodox_jordan_metropolis_7dbcc96e);
        if ("jerusalem_patriarchate".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_jerusalem_patriarchate_0c841fc7);
        if ("antioch_patriarchate".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_antioch_patriarchate_68959f82);
        if ("official_greek_orthodox".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_official_greek_orthodox_source_6588efec);
        if ("orthodox_church_in_america".equals(source)) return local(com.orthodoxprayers.privateapp.R.string.ui_orthodox_church_in_america_2a0d51a3);
        return local(com.orthodoxprayers.privateapp.R.string.ui_unavailable_24f3ca2e);
    }

    private static String shortHash(String value) {
        if (value == null || value.isEmpty()) return "—";
        return value.length() <= 16 ? value : value.substring(0, 16) + "…";
    }

    private static String safeValue(String value) {
        return value == null || value.trim().isEmpty() ? "—" : value;
    }

    private void addLanguageButton(LinearLayout row, String title, String language) {
        boolean active = language.equals(preferences.effectiveLanguage());
        boolean available = preferences.offlineLanguageEnabled(language);
        Button button = ui.button(title, active);
        button.setEnabled(available);
        button.setAlpha(available ? 1f : 0.5f);
        button.setContentDescription(title + (active
                ? local(com.orthodoxprayers.privateapp.R.string.ui_selected_language_1773d456)
                : available ? "" : local(com.orthodoxprayers.privateapp.R.string.ui_inactive_e4ed7cb2)));
        button.setOnClickListener(v -> {
            if (language.equals(preferences.effectiveLanguage())) return;
            preferences.setLanguage(language);
            preferences.setShowOriginal(false);
            preferences.clearRemoteMetadata();
            data.reloadForSelectedLanguage();
            host.navigate("settings", null);
            host.refreshData();
        });
        row.addView(button, ui.weight(60));
    }

    private String formatTimestamp(long timestamp, String fallback) {
        if (timestamp == 0L) return fallback;
        return LocalePolicy.formatTimestamp(timestamp, preferences.effectiveLanguage(), ZoneId.systemDefault());
    }

    private void showTimePicker(int currentMinute, MinuteSelection callback) {
        TimePicker picker = new TimePicker(host.activity());
        picker.setIs24HourView(true);
        picker.setHour(currentMinute / 60);
        picker.setMinute(currentMinute % 60);
        LinearLayout wrapper = new LinearLayout(host.activity());
        wrapper.setGravity(android.view.Gravity.CENTER);
        wrapper.setPadding(ui.dp(12), 0, ui.dp(12), 0);
        wrapper.addView(picker, new LinearLayout.LayoutParams(-2, -2));
        new AlertDialog.Builder(host.activity())
                .setTitle(local(com.orthodoxprayers.privateapp.R.string.ui_choose_time_afb7d8a6))
                .setView(wrapper)
                .setPositiveButton(local(com.orthodoxprayers.privateapp.R.string.ui_save_d4087fa0), (dialog, which) -> {
                    callback.onSelected(picker.getHour() * 60 + picker.getMinute());
                    host.navigate("settings", null);
                })
                .setNegativeButton(local(com.orthodoxprayers.privateapp.R.string.ui_cancel_1bd7a4b9), null)
                .show();
    }

    private interface MinuteSelection { void onSelected(int minuteOfDay); }


}
