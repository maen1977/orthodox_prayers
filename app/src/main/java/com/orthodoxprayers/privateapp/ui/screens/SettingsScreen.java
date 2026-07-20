package com.orthodoxprayers.privateapp.ui.screens;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.text.format.DateFormat;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.data.TranslationCoverage;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.Date;
import java.util.Locale;

public final class SettingsScreen extends BaseScreen {
    public SettingsScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("الإعدادات", "Settings", "Ρυθμίσεις"), true);
        page.root.addView(ui.sectionTitle(local("لغة التطبيق والنصوص", "App and text language", "Γλῶσσα ἐφαρμογῆς καὶ κειμένων")));
        TranslationCoverage.Result en = data.translationCoverage("en");
        TranslationCoverage.Result el = data.translationCoverage("el");
        LinearLayout languages = ui.row();
        addLanguageButton(languages, "العربية", "ar");
        addLanguageButton(languages, "English", "en");
        addLanguageButton(languages, "Ελληνικά", "el");
        add(page.root, languages, 0, 5);

        TextView languagePolicy = ui.infoBadge(local(
                "الواجهة مفعلة بالكامل باللغات الثلاث. كل لغة تُقرأ من مكتبتها الكنسية الأصلية المستقلة؛ ولا يترجم التطبيق نصًا من لغة إلى أخرى. عند غياب النص الأصلي المعتمد يظهر تنبيه واضح بدل نص مترجم.",
                "The interface is fully enabled in all three languages. Each language is read from its own independent official Orthodox source library; the app does not translate text from another language. Missing native text is clearly marked unavailable.",
                "Ἡ διεπαφὴ λειτουργεῖ καὶ στὶς τρεῖς γλῶσσες. Κάθε γλῶσσα φορτώνεται ἀπὸ χωριστὴ ἐπίσημη ὀρθόδοξη πηγή· ἡ ἐφαρμογὴ δὲν μεταφράζει κείμενα ἀπὸ ἄλλη γλῶσσα."
        ));
        add(page.root, languagePolicy, 0, 8);

        TextView coverage = centered(local(
                "اكتمال مكتبات النصوص الأصلية حاليًا — الإنجليزية: ",
                "Current native official-text coverage — English: ",
                "Κάλυψη πρωτότυπων ἐπίσημων κειμένων — Ἀγγλικά: "
        ) + en.percent + "%\n" + local("اليونانية: ", "Greek: ", "Ἑλληνικά: ") + el.percent + "%",
                13, ui.colors().secondaryText(), false);
        add(page.root, coverage, 0, 8);

        Button languagePacks = ui.button(local("إدارة اللغات النشطة", "Manage active languages", "Διαχείριση ἐνεργῶν γλωσσῶν"), false);
        languagePacks.setOnClickListener(v -> host.navigate("language_packs", null));
        add(page.root, languagePacks, 0, 8);

        Button original = ui.button(preferences.showOriginal()
                ? local("إخفاء النص الأصلي", "Hide source text", "Κρύψε πρωτότυπο")
                : local("إظهار النص الأصلي", "Show source text", "Δεῖξε πρωτότυπο"), preferences.showOriginal());
        original.setOnClickListener(v -> {
            preferences.setShowOriginal(!preferences.showOriginal());
            host.navigate("settings", null);
        });
        add(page.root, original, 0, 10);

        page.root.addView(ui.sectionTitle(local("القراءة", "Reading", "Ἀνάγνωση")));
        LinearLayout font = ui.row();
        Button smaller = ui.button("A−", false);
        smaller.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() - 0.1f); host.navigate("settings", null); });
        font.addView(smaller, ui.weight(48));
        Button reset = ui.button(local("عادي", "Default", "Κανονικό"), false);
        reset.setOnClickListener(v -> { preferences.setFontScale(1.0f); host.navigate("settings", null); });
        font.addView(reset, ui.weight(48));
        Button larger = ui.button("A+", false);
        larger.setOnClickListener(v -> { preferences.setFontScale(preferences.fontScale() + 0.1f); host.navigate("settings", null); });
        font.addView(larger, ui.weight(48));
        add(page.root, font, 0, 5);

        Button dark = ui.button(preferences.darkMode()
                ? local("استخدام الوضع الفاتح", "Use light mode", "Φωτεινὸ θέμα")
                : local("استخدام الوضع الليلي", "Use dark mode", "Σκοτεινὸ θέμα"), preferences.darkMode());
        dark.setOnClickListener(v -> { preferences.setDarkMode(!preferences.darkMode()); host.navigate("settings", null); });
        add(page.root, dark, 0, 6);

        Button keepOn = ui.button(preferences.keepScreenOn()
                ? local("إطفاء خيار إبقاء الشاشة مضاءة", "Disable keep-screen-on", "Ἀπενεργοποίηση ὀθόνης")
                : local("إبقاء الشاشة مضاءة أثناء الصلاة", "Keep screen on while reading", "Διατήρηση ὀθόνης"), preferences.keepScreenOn());
        keepOn.setOnClickListener(v -> { preferences.setKeepScreenOn(!preferences.keepScreenOn()); host.navigate("settings", null); });
        add(page.root, keepOn, 0, 6);

        LinearLayout spacing = ui.row();
        Button tighter = ui.button(local("تباعد أقل", "Less spacing", "Μικρότερο διάστιχο"), false);
        tighter.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(preferences.lineSpacingMultiplier() - 0.1f); host.navigate("settings", null); });
        spacing.addView(tighter, ui.weight(48));
        Button spacingReset = ui.button(local("التباعد ", "Spacing ", "Διάστιχο ") + String.format(Locale.US, "%.2f", preferences.lineSpacingMultiplier()), false);
        spacingReset.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(1.16f); host.navigate("settings", null); });
        spacing.addView(spacingReset, ui.weight(48));
        Button wider = ui.button(local("تباعد أكبر", "More spacing", "Μεγαλύτερο διάστιχο"), false);
        wider.setOnClickListener(v -> { preferences.setLineSpacingMultiplier(preferences.lineSpacingMultiplier() + 0.1f); host.navigate("settings", null); });
        spacing.addView(wider, ui.weight(48));
        add(page.root, spacing, 0, 5);

        Button fontFamily = ui.button(local("نوع الخط: ", "Font: ", "Γραμματοσειρά: ") + fontFamilyLabel(), false);
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
        Button readerTheme = ui.button(local("ثيم القارئ: ", "Reader theme: ", "Θέμα ἀναγνώστη: ") + readerThemeLabel(), false);
        readerTheme.setOnClickListener(v -> {
            String current = preferences.readerTheme();
            preferences.setReaderTheme("system".equals(current) ? "sepia" : "sepia".equals(current) ? "night" : "system");
            host.navigate("settings", null);
        });
        readerAppearance.addView(readerTheme, new LinearLayout.LayoutParams(0, -2, 2f));
        Button brightness = ui.button("☀ " + preferences.readerBrightnessPercent() + "%", false);
        brightness.setOnClickListener(v -> {
            int current = preferences.readerBrightnessPercent();
            preferences.setReaderBrightnessPercent(current > 80 ? 80 : current > 60 ? 60 : current > 40 ? 40 : current > 20 ? 20 : 100);
            host.navigate("settings", null);
        });
        readerAppearance.addView(brightness, ui.weight(48));
        add(page.root, readerAppearance, 0, 10);

        page.root.addView(ui.sectionTitle(local("التقويم والتذكيرات", "Calendar and reminders", "Ἡμερολόγιο καὶ ὑπενθυμίσεις")));
        LinearLayout quietHours = ui.row();
        Button quietStart = ui.button(local("بدء الهدوء ", "Quiet starts ", "Ἔναρξη ἡσυχίας ") + formatMinute(preferences.quietHoursStartMinute()), false);
        quietStart.setOnClickListener(v -> {
            preferences.setQuietHours((preferences.quietHoursStartMinute() + 30) % 1440, preferences.quietHoursEndMinute());
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
            host.navigate("settings", null);
        });
        quietHours.addView(quietStart, ui.weight(60));
        Button quietEnd = ui.button(local("نهاية الهدوء ", "Quiet ends ", "Λήξη ἡσυχίας ") + formatMinute(preferences.quietHoursEndMinute()), false);
        quietEnd.setOnClickListener(v -> {
            preferences.setQuietHours(preferences.quietHoursStartMinute(), (preferences.quietHoursEndMinute() + 30) % 1440);
            new ReminderScheduler(host.activity(), preferences).scheduleAll();
            host.navigate("settings", null);
        });
        quietHours.addView(quietEnd, ui.weight(60));
        add(page.root, quietHours, 0, 6);
        TextView quietNotice = centered(local(
                "لن يصدر التطبيق إشعارات خلال ساعات الهدوء المحددة.",
                "The app will not notify during the selected quiet hours.",
                "Ἡ ἐφαρμογὴ δὲν στέλνει εἰδοποιήσεις στὶς ὧρες ἡσυχίας."
        ), 12, ui.colors().secondaryText(), false);
        add(page.root, quietNotice, 0, 8);

        Button calendarMode = ui.button("julian".equals(preferences.calendarMode())
                ? local("عرض التاريخ الغريغوري فقط", "Show Gregorian dates only", "Μόνο Γρηγοριανὲς ἡμερομηνίες")
                : local("إظهار التاريخ اليولياني بجانب الغريغوري", "Show Julian dates beside Gregorian", "Ἰουλιανὴ δίπλα στὴ Γρηγοριανή"), "julian".equals(preferences.calendarMode()));
        calendarMode.setOnClickListener(v -> {
            preferences.setCalendarMode("julian".equals(preferences.calendarMode()) ? "gregorian" : "julian");
            host.navigate("settings", null);
        });
        add(page.root, calendarMode, 0, 6);

        addReminder(page.root, ReminderScheduler.MORNING, local("صلاة الصباح", "Morning prayer", "Πρωινὴ προσευχή"), 6 * 60 + 30);
        addReminder(page.root, ReminderScheduler.READING, local("قراءات اليوم", "Daily readings", "Ἡμερήσια ἀναγνώσματα"), 8 * 60);
        addReminder(page.root, ReminderScheduler.EVENING, local("صلاة المساء", "Evening prayer", "Ἑσπερινὴ προσευχή"), 21 * 60);
        addReminder(page.root, ReminderScheduler.FEAST, local("الأعياد والتذكارات", "Feasts and commemorations", "Ἑορτὲς καὶ μνῆμες"), 7 * 60);
        addReminder(page.root, ReminderScheduler.FAST, local("حالة الصيام", "Fasting status", "Κατάσταση νηστείας"), 7 * 60 + 15);
        addReminder(page.root, ReminderScheduler.PERSONAL, local("تذكير شخصي", "Personal reminder", "Προσωπικὴ ὑπενθύμιση"), 18 * 60);

        page.root.addView(ui.sectionTitle(local("التحديث والبيانات", "Update and data", "Ἐνημέρωση καὶ ἀσφάλεια")));
        Button refresh = ui.button(
                data.isRefreshing()
                        ? local("التحديث جارٍ الآن…", "Update in progress…", "Ἡ ἐνημέρωση ἐκτελεῖται…")
                        : local("تحديث بيانات اليوم الآن", "Refresh today’s data now", "Ἐνημέρωση σημερινῶν δεδομένων"),
                data.isRefreshing()
        );
        refresh.setEnabled(!data.isRefreshing());
        refresh.setOnClickListener(v -> host.refreshData());
        add(page.root, refresh, 0, 7);

        boolean exactMidnight = UpdateCoordinator.isExactMidnightEnabled(host.activity());
        Button midnightAccuracy = ui.button(exactMidnight
                ? local("تحديث منتصف الليل الدقيق: مفعّل", "Exact midnight update: enabled", "Ἀκριβὴς ἐνημέρωση μεσονυκτίου: ἐνεργή")
                : local("تفعيل التحديث الدقيق عند 00:00", "Enable exact 00:00 update", "Ἐνεργοποίηση ἀκριβοῦς ἐνημερώσεως 00:00"), exactMidnight);
        midnightAccuracy.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                    && !UpdateCoordinator.isExactMidnightEnabled(host.activity())) {
                try {
                    host.activity().startActivity(UpdateCoordinator.exactAlarmSettingsIntent(host.activity()));
                } catch (Exception error) {
                    Toast.makeText(host.activity(), local(
                            "تعذر فتح إذن المنبهات الدقيقة؛ سيبقى التحديث الاحتياطي عند منتصف الليل فعالًا.",
                            "Exact-alarm settings could not be opened; the midnight fallback remains active.",
                            "Δὲν ἄνοιξαν οἱ ρυθμίσεις· παραμένει ἡ ἐφεδρικὴ ἐνημέρωση μεσονυκτίου."
                    ), Toast.LENGTH_LONG).show();
                }
                return;
            }
            OrthodoxPrayersApp app = (OrthodoxPrayersApp) host.activity().getApplication();
            app.updateCoordinator().scheduleMidnightRefresh();
            Toast.makeText(host.activity(), local(
                    "تم تثبيت موعد التحديث اليومي عند 00:00 بتوقيت عمّان.",
                    "The daily update is scheduled for 00:00 Amman time.",
                    "Ἡ καθημερινὴ ἐνημέρωση ὁρίστηκε στὶς 00:00 ὥρα Ἀμμάν."
            ), Toast.LENGTH_SHORT).show();
        });
        add(page.root, midnightAccuracy, 0, 7);

        TextView midnightNotice = centered(local(
                "التطبيق يوقظ مهمة التحديث عند الساعة 12:00 منتصف الليل بتوقيت عمّان. إذا كان إذن المنبه الدقيق غير متاح، يستخدم النظام جدولة احتياطية لأقرب وقت يسمح به الجهاز، ويعيد المحاولة تلقائيًا عند عودة الإنترنت.",
                "The app starts its update task at 12:00 midnight Amman time. If exact-alarm access is unavailable, Android uses the closest permitted fallback and retries automatically when internet returns.",
                "Ἡ ἐνημέρωση ξεκινᾷ στὶς 00:00 ὥρα Ἀμμάν. Ἂν δὲν ἐπιτρέπεται ἀκριβὴς συναγερμός, χρησιμοποιεῖται ἡ πλησιέστερη ἐπιτρεπτὴ ἐφεδρικὴ ἐκτέλεση."
        ), 12, ui.colors().secondaryText(), false);
        add(page.root, midnightNotice, 0, 8);

        String lastUpdate = formatTimestamp(preferences.lastSuccessfulUpdate(),
                local("لم ينجح تحديث شبكي بعد", "No successful network update yet", "Χωρὶς ἐπιτυχῆ ἐνημέρωση"));
        String lastAttempt = formatTimestamp(preferences.lastRefreshAttempt(),
                local("لم تُجرَ محاولة بعد", "No attempt has been made yet", "Χωρὶς προσπάθεια"));
        String dateValue = data.dataDate().isEmpty()
                ? local("غير متوفر", "Unavailable", "Μὴ διαθέσιμο")
                : data.dataDate();
        TextView updateState = data.isRefreshing()
                ? ui.infoBadge(data.userFacingRefreshStatus())
                : ui.badge(data.userFacingRefreshStatus(), preferences.lastRefreshSucceeded() && data.isTodayCurrent());
        add(page.root, updateState, 0, 8);

        TextView status = centered(local("إصدار التطبيق: ", "App version: ", "Ἔκδοση: ") + BuildConfig.VERSION_NAME
                + "\n" + local("تاريخ البيانات المعروضة: ", "Displayed data date: ", "Ἡμερομηνία δεδομένων: ") + dateValue
                + "\n" + local("آخر محاولة تحديث: ", "Last update attempt: ", "Τελευταία προσπάθεια: ") + lastAttempt
                + "\n" + local("آخر فحص ناجح: ", "Last successful check: ", "Τελευταῖος ἐπιτυχὴς ἔλεγχος: ") + lastUpdate
                + "\n" + local("رمز تشخيص التحديث: ", "Update diagnostic code: ", "Κωδικὸς διαγνώσεως: ") + data.refreshDiagnosticCode()
                + "\n" + local("مصدر النسخة: ", "Trusted copy source: ", "Πηγὴ ἀντιγράφου: ") + trustSourceLabel()
                + "\n" + local("بصمة المحتوى: ", "Content fingerprint: ", "Ἀποτύπωμα: ") + shortHash(data.contentHash())
                + "\n" + local("مرجع النص الكتابي: ", "Scripture source ID: ", "Πηγὴ Γραφῆς: ") + safeValue(data.canonicalSourceId())
                + "\n" + local("المصدر الرسمي المختار لليوم: ", "Selected official source: ", "Ἐπιλεγμένη ἐπίσημη πηγή: ") + officialSourceLabel(data.selectedOfficialSource())
                + "\n" + local("التحديث التلقائي: عند 00:00 منتصف الليل بتوقيت عمّان، مع فحص احتياطي عند فتح التطبيق", "Automatic update: at 00:00 midnight Amman time, with a safety check when the app opens", "Αὐτόματη ἐνημέρωση στὶς 00:00 ὥρα Ἀμμάν, μὲ ἐφεδρικὸ ἔλεγχο στὸ ἄνοιγμα")
                + "\n" + local("التحقق: HTTPS + توقيع رقمي مستقل + مخطط البيانات + سلامة النص الكتابي", "Verification: HTTPS + independent digital signature + schema + Scripture integrity", "Ἔλεγχος: HTTPS, ψηφιακὴ ὑπογραφή, σχῆμα καὶ ἀκεραιότητα"),
                13, ui.colors().secondaryText(), false);
        add(page.root, status, 0, 8);

        page.root.addView(ui.sectionTitle(local("المصادر والمراجع", "Sources and references", "Πηγὲς καὶ παραπομπές")));
        int registeredSourceCount = data.registeredSources().length();
        TextView sourceRegistryNotice = ui.infoBadge(local(
                "يعرض التطبيق " + registeredSourceCount + " مصدرًا مسجلًا للمحتوى والتقويم والقراءات، مع نوع الاستخدام والرابط وحالة الحقوق وآخر تحقق.",
                "The app lists " + registeredSourceCount + " registered content, calendar, and Scripture sources with use, link, rights, and verification details.",
                "Ἡ ἐφαρμογὴ παραθέτει " + registeredSourceCount + " καταχωρισμένες πηγές μὲ χρήση, σύνδεσμο καὶ κατάσταση δικαιωμάτων."
        ));
        add(page.root, sourceRegistryNotice, 0, 7);
        Button sources = ui.button(local("عرض جميع المصادر", "View all sources", "Προβολὴ ὅλων τῶν πηγῶν"), false);
        sources.setOnClickListener(v -> host.navigate("sources", null));
        add(page.root, sources, 0, 10);

        String sourceNote = data.sourceNote();
        if (!sourceNote.isEmpty()) {
            TextView source = centered(local("عن مصدر المحتوى: ", "About the content source: ", "Περὶ πηγῆς: ") + sourceNote,
                    13, ui.colors().secondaryText(), false);
            add(page.root, source, 0, 8);
        }
        // R14_SETTINGS_CLEANUP: keep the free-app notice but hide call/privacy actions.
        page.root.addView(ui.sectionTitle(local("عن البرنامج", "About the app", "Περὶ τῆς ἐφαρμογῆς")));
        LinearLayout aboutCard = ui.card();
        TextView freeNotice = centered(local(
                "هذا البرنامج مجاني، ومقدم من معن حنونة للستلايت.\nرقم الهاتف: 00962788272988",
                "This application is free and is presented by Maen Hanouna Satellite.\nPhone: 00962788272988",
                "Ἡ ἐφαρμογὴ παρέχεται δωρεὰν ἀπὸ τὸ Maen Hanouna Satellite.\nΤηλέφωνο: 00962788272988"
        ), 15, ui.colors().primaryText(), true);
        freeNotice.setTextIsSelectable(true);
        aboutCard.addView(freeNotice);
        add(page.root, aboutCard, 0, 10);

        TextView privacy = centered(local("لا إعلانات، لا تسجيل دخول، ولا تتبع. لا توجد مفاتيح خاصة داخل التطبيق.",
                "No ads, login, or tracking. No private keys are stored in the app.",
                "Χωρὶς διαφημίσεις, σύνδεση ἢ παρακολούθηση."), 13, ui.colors().secondaryText(), false);
        add(page.root, privacy, 0, 16);
        return page.scroll;
    }

    private void addReminder(LinearLayout root, String kind, String label, int fallbackMinute) {
        LinearLayout row = ui.row();
        boolean enabled = preferences.remindersEnabled(kind);
        Button toggle = ui.button((enabled ? "🔔 " : "🔕 ") + label, enabled);
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
        time.setOnClickListener(v -> {
            int nextMinute = (preferences.reminderMinuteOfDay(kind, fallbackMinute) + 30) % 1440;
            preferences.setReminderMinuteOfDay(kind, nextMinute);
            if (preferences.remindersEnabled(kind)) new ReminderScheduler(host.activity(), preferences).schedule(kind);
            host.navigate("settings", null);
        });
        row.addView(time, ui.weight(48));
        add(root, row, 0, 5);
    }

    private String autoScrollSettingLabel() {
        int speed = preferences.autoScrollSpeed();
        return speed == 0
                ? local("التمرير التلقائي: متوقف", "Auto-scroll: off", "Αὐτόματη κύλιση: κλειστή")
                : local("سرعة التمرير التلقائي: ", "Auto-scroll speed: ", "Ταχύτητα αὐτόματης κύλισης: ") + speed;
    }

    private String readerThemeLabel() {
        String theme = preferences.readerTheme();
        if ("sepia".equals(theme)) return local("ورقي", "Sepia", "Σέπια");
        if ("night".equals(theme)) return local("ليلي", "Night", "Νύχτα");
        return local("النظام", "System", "Σύστημα");
    }

    private String fontFamilyLabel() {
        if ("serif".equals(preferences.fontFamily())) return local("كتاب", "Serif", "Serif");
        if ("monospace".equals(preferences.fontFamily())) return local("ثابت العرض", "Monospace", "Monospace");
        return local("بسيط", "Sans", "Sans");
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
