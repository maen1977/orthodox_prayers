package com.orthodoxprayers.privateapp.ui.screens;

import android.Manifest;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.os.Build;
import android.text.format.DateFormat;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.data.TranslationCoverage;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.Date;
import java.util.Locale;

public final class SettingsScreen extends BaseScreen {
    public SettingsScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("الإعدادات", "Settings", "Ρυθμίσεις"), true);
        addLanguageAndAppearance(page.root);
        addReadingSettings(page.root);
        addCalendarAndReminders(page.root);
        addDataAndSources(page.root);
        JSONObject liturgyCoverage = data.serviceCoverage("divine_liturgy");
        if (liturgyCoverage != null) {
            TextView liturgyCoverageBadge = ui.infoBadge(local("اكتمال القطع اليومية المتغيرة للقداس: ", "Verified variable Liturgy coverage: ", "Κάλυψη μεταβλητῶν κειμένων: ")
                    + liturgyCoverage.optInt("coverage_percent", 0) + "%");
            add(page.root, liturgyCoverageBadge, 0, 7);
        }
        addAbout(page.root);
        return page.scroll;
    }

    private void addLanguageAndAppearance(LinearLayout root) {
        root.addView(ui.sectionTitle(local("اللغة والمظهر", "Language and appearance", "Γλῶσσα καὶ ἐμφάνιση")));
        LinearLayout card = ui.elevatedCard();

        TextView languageTitle = ui.text(local("لغة التطبيق والنصوص", "App and text language", "Γλῶσσα ἐφαρμογῆς"), 15, ui.colors().primaryText(), true);
        card.addView(languageTitle);
        LinearLayout languages = ui.row();
        addLanguageButton(languages, "العربية", "ar");
        addLanguageButton(languages, "English", "en");
        addLanguageButton(languages, "Ελληνικά", "el");
        card.addView(languages, ui.margins(-1, -2, 0, 8, 0, 4));

        TranslationCoverage.Result en = data.translationCoverage("en");
        TranslationCoverage.Result el = data.translationCoverage("el");
        TextView coverage = ui.text(local("اكتمال النصوص الأصلية — الإنجليزية: ", "Native-text coverage — English: ", "Κάλυψη πρωτότυπων κειμένων — Ἀγγλικά: ")
                + en.percent + "%  •  " + local("اليونانية: ", "Greek: ", "Ἑλληνικά: ") + el.percent + "%",
                12, ui.colors().secondaryText(), false);
        coverage.setGravity(Gravity.CENTER);
        card.addView(coverage, ui.margins(-1, -2, 0, 2, 0, 8));
        TextView languagePolicy = ui.infoBadge(local(
                "كل لغة تُقرأ من مكتبتها الكنسية الأصلية المستقلة، ولا يستبدل التطبيق النص الأصلي بترجمة آلية.",
                "Each language is read from its own independent official Orthodox library; the app does not replace native text with machine translation.",
                "Κάθε γλῶσσα διαβάζεται ἀπὸ τὴ δική της ἀνεξάρτητη ἐπίσημη ὀρθόδοξη βιβλιοθήκη."
        ));
        card.addView(languagePolicy, ui.margins(-1, -2, 0, 2, 0, 8));

        Button languagePacks = ui.smallButton(local("إدارة اللغات المتاحة دون إنترنت", "Manage offline languages", "Διαχείριση γλωσσῶν ἐκτὸς σύνδεσης"), false);
        languagePacks.setOnClickListener(v -> host.navigate("language_packs", null));
        card.addView(languagePacks, ui.margins(-1, -2, 0, 3, 0, 8));
        card.addView(ui.divider(), new LinearLayout.LayoutParams(-1, ui.dp(1)));

        addToggle(card,
                local("الوضع الداكن", "Dark mode", "Σκοτεινὸ θέμα"),
                local("واجهة مريحة للقراءة في الإضاءة المنخفضة", "A comfortable interface in low light", "Ἄνετη ἀνάγνωση σὲ χαμηλὸ φωτισμό"),
                preferences.darkMode(),
                (button, checked) -> {
                    preferences.setDarkMode(checked);
                    host.navigate("settings", null);
                });
        addToggle(card,
                local("إظهار النص الأصلي", "Show source text", "Προβολὴ πρωτοτύπου"),
                local("يعرض النص بلغته الأصلية عند توفره", "Display the original-language text when available", "Προβολὴ τοῦ πρωτοτύπου ὅταν διατίθεται"),
                preferences.showOriginal(),
                (button, checked) -> {
                    preferences.setShowOriginal(checked);
                    host.navigate("settings", null);
                });
        add(root, card, 0, 10);
    }

    private void addReadingSettings(LinearLayout root) {
        root.addView(ui.sectionTitle(local("تجربة القراءة", "Reading experience", "Ἐμπειρία ἀναγνώσεως")));
        LinearLayout card = ui.elevatedCard();

        card.addView(ui.text(local("حجم النص", "Text size", "Μέγεθος κειμένου"), 15, ui.colors().primaryText(), true));
        LinearLayout font = ui.row();
        Button smaller = ui.button("A−", false);
        smaller.setContentDescription(local("تصغير الخط", "Decrease text size", "Μείωση γραμματοσειρᾶς"));
        smaller.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() - 0.1f); host.navigate("settings", null); });
        font.addView(smaller, ui.weight(48));
        Button reset = ui.button(local("افتراضي", "Default", "Προεπιλογή"), false);
        reset.setOnClickListener(v -> { preferences.setFontScale(1.0f); host.navigate("settings", null); });
        font.addView(reset, ui.weight(48));
        Button larger = ui.button("A+", false);
        larger.setContentDescription(local("تكبير الخط", "Increase text size", "Αὔξηση γραμματοσειρᾶς"));
        larger.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() + 0.1f); host.navigate("settings", null); });
        font.addView(larger, ui.weight(48));
        card.addView(font, ui.margins(-1, -2, 0, 7, 0, 5));

        LinearLayout typography = ui.row();
        Button fontFamily = ui.button(local("نوع الخط: ", "Font: ", "Γραμματοσειρά: ") + fontFamilyLabel(), false);
        fontFamily.setOnClickListener(v -> {
            preferences.setFontFamily("serif".equals(preferences.fontFamily()) ? "sans" : "serif");
            host.navigate("settings", null);
        });
        typography.addView(fontFamily, new LinearLayout.LayoutParams(0, -2, 1.25f));
        Button spacing = ui.button(local("تباعد: ", "Spacing: ", "Διάστιχο: ") + String.format(Locale.US, "%.2f", preferences.lineSpacingMultiplier()), false);
        spacing.setOnClickListener(v -> {
            float next = preferences.lineSpacingMultiplier() >= 1.55f ? 1.0f : preferences.lineSpacingMultiplier() + 0.15f;
            preferences.setLineSpacingMultiplier(next);
            host.navigate("settings", null);
        });
        typography.addView(spacing, ui.weight(48));
        card.addView(typography, ui.margins(-1, -2, 4, 0, 4, 7));
        card.addView(ui.divider(), new LinearLayout.LayoutParams(-1, ui.dp(1)));

        addToggle(card,
                local("إبقاء الشاشة مضاءة", "Keep screen on", "Διατήρηση ὀθόνης"),
                local("يمنع انطفاء الشاشة أثناء قراءة الصلاة", "Prevents the screen from sleeping while reading", "Ἡ ὀθόνη παραμένει ἀναμμένη"),
                preferences.keepScreenOn(),
                (button, checked) -> {
                    preferences.setKeepScreenOn(checked);
                    host.navigate("settings", null);
                });

        LinearLayout readerTools = ui.row();
        Button autoScroll = ui.button(autoScrollSettingLabel(), preferences.autoScrollSpeed() > 0);
        autoScroll.setOnClickListener(v -> {
            int speed = preferences.autoScrollSpeed();
            preferences.setAutoScrollSpeed(speed >= 4 ? 0 : speed + 1);
            host.navigate("settings", null);
        });
        readerTools.addView(autoScroll, new LinearLayout.LayoutParams(0, -2, 1.2f));
        Button readerTheme = ui.button(local("القارئ: ", "Reader: ", "Ἀναγνώστης: ") + readerThemeLabel(), false);
        readerTheme.setOnClickListener(v -> {
            String current = preferences.readerTheme();
            preferences.setReaderTheme("system".equals(current) ? "sepia" : "sepia".equals(current) ? "night" : "system");
            host.navigate("settings", null);
        });
        readerTools.addView(readerTheme, ui.weight(48));
        card.addView(readerTools, ui.margins(-1, -2, 4, 4, 4, 5));

        Button brightness = ui.smallButton(local("سطوع القارئ: ", "Reader brightness: ", "Φωτεινότητα: ") + preferences.readerBrightnessPercent() + "%", false);
        brightness.setOnClickListener(v -> {
            int current = preferences.readerBrightnessPercent();
            preferences.setReaderBrightnessPercent(current > 80 ? 80 : current > 60 ? 60 : current > 40 ? 40 : current > 20 ? 20 : 100);
            host.navigate("settings", null);
        });
        card.addView(brightness, ui.margins(-1, -2, 0, 2, 0, 0));
        add(root, card, 0, 10);
    }

    private void addCalendarAndReminders(LinearLayout root) {
        root.addView(ui.sectionTitle(local("التقويم والتذكيرات", "Calendar and reminders", "Ἡμερολόγιο καὶ ὑπενθυμίσεις")));
        LinearLayout card = ui.elevatedCard();

        addToggle(card,
                local("إظهار التاريخ اليولياني", "Show Julian date", "Προβολὴ Ἰουλιανῆς ἡμερομηνίας"),
                local("يظهر بجانب التاريخ الغريغوري", "Displayed beside the Gregorian date", "Δίπλα στὴ Γρηγοριανὴ ἡμερομηνία"),
                "julian".equals(preferences.calendarMode()),
                (button, checked) -> {
                    preferences.setCalendarMode(checked ? "julian" : "gregorian");
                    host.navigate("settings", null);
                });

        card.addView(ui.divider(), ui.margins(-1, ui.dp(1), 0, 5, 0, 8));
        card.addView(ui.text(local("ساعات الهدوء", "Quiet hours", "Ὧρες ἡσυχίας"), 15, ui.colors().primaryText(), true));
        LinearLayout quietHours = ui.row();
        Button quietStart = ui.button(local("من ", "From ", "Ἀπὸ ") + formatMinute(preferences.quietHoursStartMinute()), false);
        quietStart.setOnClickListener(v -> {
            preferences.setQuietHours((preferences.quietHoursStartMinute() + 30) % 1440, preferences.quietHoursEndMinute());
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
            host.navigate("settings", null);
        });
        quietHours.addView(quietStart, ui.weight(48));
        Button quietEnd = ui.button(local("إلى ", "To ", "Ἕως ") + formatMinute(preferences.quietHoursEndMinute()), false);
        quietEnd.setOnClickListener(v -> {
            preferences.setQuietHours(preferences.quietHoursStartMinute(), (preferences.quietHoursEndMinute() + 30) % 1440);
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
            host.navigate("settings", null);
        });
        quietHours.addView(quietEnd, ui.weight(48));
        card.addView(quietHours, ui.margins(-1, -2, 0, 5, 0, 8));

        card.addView(ui.text(local("التذكيرات", "Reminders", "Ὑπενθυμίσεις"), 15, ui.colors().primaryText(), true));
        addReminder(card, ReminderScheduler.MORNING, local("صلاة الصباح", "Morning prayer", "Πρωινὴ προσευχή"), 6 * 60 + 30);
        addReminder(card, ReminderScheduler.READING, local("قراءات اليوم", "Daily readings", "Ἡμερήσια ἀναγνώσματα"), 8 * 60);
        addReminder(card, ReminderScheduler.EVENING, local("صلاة المساء", "Evening prayer", "Ἑσπερινὴ προσευχή"), 21 * 60);
        addReminder(card, ReminderScheduler.FEAST, local("الأعياد والتذكارات", "Feasts and commemorations", "Ἑορτὲς καὶ μνῆμες"), 7 * 60);
        addReminder(card, ReminderScheduler.FAST, local("حالة الصيام", "Fasting status", "Κατάσταση νηστείας"), 7 * 60 + 15);
        addReminder(card, ReminderScheduler.PERSONAL, local("تذكير شخصي", "Personal reminder", "Προσωπικὴ ὑπενθύμιση"), 18 * 60);
        add(root, card, 0, 10);
    }

    private void addDataAndSources(LinearLayout root) {
        root.addView(ui.sectionTitle(local("البيانات والمصادر", "Data and sources", "Δεδομένα καὶ πηγές")));
        LinearLayout card = ui.elevatedCard();
        Button refresh = ui.button(data.isRefreshing()
                ? local("التحديث جارٍ الآن…", "Update in progress…", "Ἡ ἐνημέρωση ἐκτελεῖται…")
                : local("تحديث بيانات اليوم", "Refresh today’s data", "Ἐνημέρωση σημερινῶν δεδομένων"), true);
        refresh.setEnabled(!data.isRefreshing());
        refresh.setAlpha(data.isRefreshing() ? 0.65f : 1f);
        refresh.setOnClickListener(v -> host.refreshData());
        card.addView(refresh);

        TextView updateState = data.isRefreshing()
                ? ui.infoBadge(data.userFacingRefreshStatus())
                : ui.badge(data.userFacingRefreshStatus(), preferences.lastRefreshSucceeded() && data.isTodayCurrent());
        card.addView(updateState, ui.margins(-1, -2, 0, 8, 0, 8));

        String lastUpdate = formatTimestamp(preferences.lastSuccessfulUpdate(), local("لا يوجد تحديث شبكي ناجح بعد", "No successful network update yet", "Χωρὶς ἐπιτυχῆ ἐνημέρωση"));
        TextView summary = ui.text(local("إصدار التطبيق: ", "App version: ", "Ἔκδοση: ") + BuildConfig.VERSION_NAME
                + "\n" + local("تاريخ البيانات: ", "Data date: ", "Ἡμερομηνία δεδομένων: ") + safeValue(data.dataDate())
                + "\n" + local("آخر فحص ناجح: ", "Last successful check: ", "Τελευταῖος ἔλεγχος: ") + lastUpdate,
                13, ui.colors().secondaryText(), false);
        summary.setTextIsSelectable(true);
        card.addView(summary, ui.margins(-1, -2, 0, 4, 0, 8));

        Button technical = ui.smallButton(local("التفاصيل التقنية والتحقق", "Technical and verification details", "Τεχνικὲς λεπτομέρειες"), false);
        technical.setOnClickListener(v -> showTechnicalDetails());
        card.addView(technical, ui.margins(-1, -2, 0, 2, 0, 6));

        LinearLayout links = ui.row();
        Button sources = ui.button(local("المصادر", "Sources", "Πηγές"), false);
        sources.setOnClickListener(v -> host.navigate("sources", null));
        links.addView(sources, ui.weight(48));
        Button churches = ui.button(local("الكنائس والبث", "Churches and live", "Ναοὶ καὶ ζωντανά"), false);
        churches.setOnClickListener(v -> host.navigate("churches", null));
        links.addView(churches, ui.weight(48));
        card.addView(links);
        add(root, card, 0, 10);
    }

    private void addAbout(LinearLayout root) {
        root.addView(ui.sectionTitle(local("عن البرنامج", "About the app", "Περὶ τῆς ἐφαρμογῆς")));
        LinearLayout card = ui.elevatedCard();
        TextView freeNotice = centered(local(
                "هذا البرنامج مجاني، ومقدم من معن حنونة للستلايت.\nرقم الهاتف: 00962788272988",
                "This application is free and is presented by Maen Hanouna Satellite.\nPhone: 00962788272988",
                "Ἡ ἐφαρμογὴ παρέχεται δωρεὰν ἀπὸ τὸ Maen Hanouna Satellite.\nΤηλέφωνο: 00962788272988"
        ), 15, ui.colors().primaryText(), true);
        freeNotice.setTextIsSelectable(true);
        card.addView(freeNotice);
        card.addView(ui.divider(), ui.margins(-1, ui.dp(1), 0, 12, 0, 12));
        TextView privacy = centered(local(
                "لا إعلانات، لا تسجيل دخول، ولا تتبع. الملاحظات والمفضلة تحفظ على جهازك.",
                "No ads, login, or tracking. Notes and favorites stay on your device.",
                "Χωρὶς διαφημίσεις, σύνδεση ἢ παρακολούθηση."
        ), 13, ui.colors().secondaryText(), false);
        card.addView(privacy);
        add(root, card, 0, 22);
    }

    private void addToggle(LinearLayout root, String title, String summary, boolean checked,
                           CompoundButton.OnCheckedChangeListener listener) {
        LinearLayout row = ui.row();
        row.setPadding(0, ui.dp(10), 0, ui.dp(10));
        LinearLayout text = new LinearLayout(host.activity());
        text.setOrientation(LinearLayout.VERTICAL);
        text.addView(ui.text(title, 15, ui.colors().primaryText(), true));
        if (summary != null && !summary.isEmpty()) {
            text.addView(ui.text(summary, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
        }
        row.addView(text, new LinearLayout.LayoutParams(0, -2, 1f));
        Switch toggle = new Switch(host.activity());
        toggle.setChecked(checked);
        toggle.setContentDescription(title);
        toggle.setThumbTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_checked}, new int[]{}},
                new int[]{ThemePalette.GOLD, ui.colors().secondaryText()}
        ));
        toggle.setTrackTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_checked}, new int[]{}},
                new int[]{ThemePalette.NAVY_2, ui.colors().divider()}
        ));
        toggle.setOnCheckedChangeListener(listener);
        row.addView(toggle, new LinearLayout.LayoutParams(-2, -2));
        root.addView(row, new LinearLayout.LayoutParams(-1, -2));
    }

    private void addReminder(LinearLayout root, String kind, String label, int fallbackMinute) {
        LinearLayout row = ui.row();
        row.setPadding(0, ui.dp(5), 0, ui.dp(5));
        boolean enabled = preferences.remindersEnabled(kind);

        LinearLayout text = new LinearLayout(host.activity());
        text.setOrientation(LinearLayout.VERTICAL);
        text.addView(ui.text(label, 14, ui.colors().primaryText(), true));
        text.addView(ui.text(formatMinute(preferences.reminderMinuteOfDay(kind, fallbackMinute)), 12, ui.colors().secondaryText(), false));
        row.addView(text, new LinearLayout.LayoutParams(0, -2, 1f));

        Button time = ui.smallButton(local("تغيير الوقت", "Change time", "Ἀλλαγὴ ὥρας"), false);
        time.setOnClickListener(v -> {
            int nextMinute = (preferences.reminderMinuteOfDay(kind, fallbackMinute) + 30) % 1440;
            preferences.setReminderMinuteOfDay(kind, nextMinute);
            if (preferences.remindersEnabled(kind)) new ReminderScheduler(host.activity(), preferences).schedule(kind);
            host.navigate("settings", null);
        });
        row.addView(time, new LinearLayout.LayoutParams(ui.dp(112), -2));

        Switch toggle = new Switch(host.activity());
        toggle.setChecked(enabled);
        toggle.setContentDescription(label);
        toggle.setOnCheckedChangeListener((button, checked) -> {
            if (checked && Build.VERSION.SDK_INT >= 33
                    && host.activity().checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                button.setChecked(false);
                preferences.setPendingReminderKind(kind);
                host.activity().requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, ReminderScheduler.NOTIFICATION_PERMISSION_REQUEST);
                return;
            }
            preferences.setRemindersEnabled(kind, checked);
            ReminderScheduler scheduler = new ReminderScheduler(host.activity(), preferences);
            if (checked) scheduler.schedule(kind); else scheduler.cancel(kind);
        });
        row.addView(toggle, ui.margins(-2, -2, 8, 0, 0, 0));
        root.addView(row, new LinearLayout.LayoutParams(-1, -2));
    }

    private void showTechnicalDetails() {
        TextView text = ui.text(technicalDetails(), 13, ui.colors().primaryText(), false);
        text.setTextIsSelectable(true);
        text.setPadding(ui.dp(18), ui.dp(12), ui.dp(18), ui.dp(18));
        ScrollView scroll = new ScrollView(host.activity());
        scroll.addView(text, new ScrollView.LayoutParams(-1, -2));
        new AlertDialog.Builder(host.activity())
                .setTitle(local("تفاصيل البيانات والتحقق", "Data and verification details", "Λεπτομέρειες δεδομένων"))
                .setView(scroll)
                .setPositiveButton(local("إغلاق", "Close", "Κλείσιμο"), null)
                .show();
    }

    private String technicalDetails() {
        String lastAttempt = formatTimestamp(preferences.lastRefreshAttempt(), local("لم تُجرَ محاولة بعد", "No attempt yet", "Χωρὶς προσπάθεια"));
        String lastUpdate = formatTimestamp(preferences.lastSuccessfulUpdate(), local("لا يوجد تحديث ناجح بعد", "No successful update yet", "Χωρὶς ἐπιτυχῆ ἐνημέρωση"));
        return local("إصدار التطبيق: ", "App version: ", "Ἔκδοση: ") + BuildConfig.VERSION_NAME
                + "\n" + local("تاريخ البيانات المعروضة: ", "Displayed data date: ", "Ἡμερομηνία δεδομένων: ") + safeValue(data.dataDate())
                + "\n" + local("آخر محاولة تحديث: ", "Last update attempt: ", "Τελευταία προσπάθεια: ") + lastAttempt
                + "\n" + local("آخر فحص ناجح: ", "Last successful check: ", "Τελευταῖος ἐπιτυχὴς ἔλεγχος: ") + lastUpdate
                + "\n" + local("رمز التشخيص: ", "Diagnostic code: ", "Κωδικὸς διαγνώσεως: ") + data.refreshDiagnosticCode()
                + "\n" + local("مراجعة بيان التحديث: ", "Manifest revision: ", "Ἀναθεώρηση: ") + preferences.acceptedManifestRevisionForDate(data.dataDate())
                + "\n" + local("مصدر النسخة الموثوقة: ", "Trusted copy source: ", "Πηγὴ ἀντιγράφου: ") + trustSourceLabel()
                + "\n" + local("بصمة المحتوى: ", "Content fingerprint: ", "Ἀποτύπωμα: ") + shortHash(data.contentHash())
                + "\n" + local("مرجع النص الكتابي: ", "Scripture source ID: ", "Πηγὴ Γραφῆς: ") + safeValue(data.canonicalSourceId())
                + "\n" + local("المصدر الرسمي لليوم: ", "Official source for today: ", "Ἐπίσημη πηγή: ") + officialSourceLabel(data.selectedOfficialSource())
                + "\n" + local("التحديث التلقائي: 00:05 بتوقيت عمّان، مع فحص تصحيحات اليوم كل 30 دقيقة أثناء الاستخدام.",
                "Automatic update: 00:05 Amman time, with same-day correction checks every 30 minutes while the app is used.",
                "Αὐτόματη ἐνημέρωση: 00:05 ὥρα Ἀμμάν, μὲ ἔλεγχο διορθώσεων κάθε 30 minutes.")
                + "\n\n" + local("التحقق المستخدم: اتصال HTTPS، توقيع رقمي مستقل، فحص مخطط البيانات، وفحص سلامة النصوص.",
                "Verification uses HTTPS, an independent digital signature, schema validation, and Scripture integrity checks.",
                "Ἔλεγχος μὲ HTTPS, ψηφιακὴ ὑπογραφή καὶ ἀκεραιότητα κειμένων.");
    }

    private String autoScrollSettingLabel() {
        int speed = preferences.autoScrollSpeed();
        return speed == 0
                ? local("التمرير التلقائي: متوقف", "Auto-scroll: off", "Αὐτόματη κύλιση: κλειστή")
                : local("التمرير التلقائي: سرعة ", "Auto-scroll: speed ", "Αὐτόματη κύλιση: ") + speed;
    }

    private String readerThemeLabel() {
        String theme = preferences.readerTheme();
        if ("sepia".equals(theme)) return local("ورقي", "Sepia", "Σέπια");
        if ("night".equals(theme)) return local("ليلي", "Night", "Νύχτα");
        return local("النظام", "System", "Σύστημα");
    }

    private String fontFamilyLabel() {
        return "serif".equals(preferences.fontFamily()) ? local("كتابي", "Serif", "Serif") : local("حديث", "Modern sans", "Sans");
    }

    private static String formatMinute(int minuteOfDay) {
        return String.format(Locale.US, "%02d:%02d", minuteOfDay / 60, minuteOfDay % 60);
    }

    private String trustSourceLabel() {
        String source = data.trustSource();
        if ("signed_remote".equals(source)) return local("تحديث شبكي موقّع", "Signed network update", "Ὑπογεγραμμένη ἐνημέρωση");
        if ("signed_cache".equals(source)) return local("نسخة محلية موقّعة", "Signed local copy", "Ὑπογεγραμμένο τοπικὸ ἀντίγραφο");
        if ("signed_backup".equals(source)) return local("آخر نسخة احتياطية موثوقة", "Last trusted backup", "Ἔμπιστο ἀντίγραφο");
        if ("signed_embedded".equals(source)) return local("نسخة مضمّنة موقّعة", "Signed embedded copy", "Ἐνσωματωμένο ἀντίγραφο");
        return local("غير معروف", "Unknown", "Ἄγνωστο");
    }

    private String officialSourceLabel(String source) {
        if ("orthodox_jordan".equals(source)) return local("مطرانية الروم الأرثوذكس في الأردن", "Orthodox Jordan Metropolis", "Μητρόπολη Ἰορδανίας");
        if ("jerusalem_patriarchate".equals(source)) return local("بطريركية القدس", "Jerusalem Patriarchate", "Πατριαρχεῖο Ἱεροσολύμων");
        if ("antioch_patriarchate".equals(source)) return local("بطريركية أنطاكية", "Antioch Patriarchate", "Πατριαρχεῖο Ἀντιοχείας");
        if ("official_greek_orthodox".equals(source)) return local("مصدر يوناني أرثوذكسي رسمي", "Official Greek Orthodox source", "Ἐπίσημη ἑλληνικὴ ὀρθόδοξη πηγή");
        if ("orthodox_church_in_america".equals(source)) return local("الكنيسة الأرثوذكسية في أمريكا", "Orthodox Church in America", "Ὀρθόδοξη Ἐκκλησία στὴν Ἀμερική");
        return local("غير متوفر", "Unavailable", "Μὴ διαθέσιμο");
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
                ? local(" — اللغة المحددة", " — selected language", " — ἐπιλεγμένη γλῶσσα")
                : available ? "" : local(" — غير نشطة", " — inactive", " — ἀνενεργή")));
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
        return DateFormat.getMediumDateFormat(host.activity()).format(new Date(timestamp)) + " "
                + DateFormat.getTimeFormat(host.activity()).format(new Date(timestamp));
    }
}
