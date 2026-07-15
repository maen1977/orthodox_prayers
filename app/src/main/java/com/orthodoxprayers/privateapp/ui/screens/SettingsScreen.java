package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.net.Uri;
import android.text.format.DateFormat;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.data.TranslationCoverage;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.Date;

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
        add(page.root, keepOn, 0, 10);

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
                + "\n" + local("مصدر النسخة: ", "Trusted copy source: ", "Πηγὴ ἀντιγράφου: ") + trustSourceLabel()
                + "\n" + local("بصمة المحتوى: ", "Content fingerprint: ", "Ἀποτύπωμα: ") + shortHash(data.contentHash())
                + "\n" + local("مرجع النص الكتابي: ", "Scripture source ID: ", "Πηγὴ Γραφῆς: ") + safeValue(data.canonicalSourceId())
                + "\n" + local("المصدر الرسمي المختار لليوم: ", "Selected official source: ", "Ἐπιλεγμένη ἐπίσημη πηγή: ") + officialSourceLabel(data.selectedOfficialSource())
                + "\n" + local("التحديث التلقائي: فحص عند فتح التطبيق، ثم عند 00:00 و00:15 بتوقيت عمّان، مع فحص احتياطي دوري", "Automatic update: on app open, at 00:00 and 00:15 Amman time, plus a periodic safety check", "Αὐτόματη ἐνημέρωση στὸ ἄνοιγμα, στὶς 00:00 καὶ 00:15 ὥρα Ἀμμάν")
                + "\n" + local("التحقق: HTTPS + توقيع رقمي مستقل + مخطط البيانات + سلامة النص الكتابي", "Verification: HTTPS + independent digital signature + schema + Scripture integrity", "Ἔλεγχος: HTTPS, ψηφιακὴ ὑπογραφή, σχῆμα καὶ ἀκεραιότητα"),
                13, ui.colors().secondaryText(), false);
        add(page.root, status, 0, 8);
        String sourceNote = data.sourceNote();
        if (!sourceNote.isEmpty()) {
            TextView source = centered(local("عن مصدر المحتوى: ", "About the content source: ", "Περὶ πηγῆς: ") + sourceNote,
                    13, ui.colors().secondaryText(), false);
            add(page.root, source, 0, 8);
        }
        page.root.addView(ui.sectionTitle(local("عن البرنامج", "About the app", "Περὶ τῆς ἐφαρμογῆς")));
        LinearLayout aboutCard = ui.card();
        TextView freeNotice = centered(local(
                "هذا البرنامج مجاني، ومقدم من معن حنونة للستلايت.\nرقم الهاتف: 00962788272988",
                "This application is free and is presented by Maen Hanouna Satellite.\nPhone: 00962788272988",
                "Ἡ ἐφαρμογὴ παρέχεται δωρεὰν ἀπὸ τὸ Maen Hanouna Satellite.\nΤηλέφωνο: 00962788272988"
        ), 15, ui.colors().primaryText(), true);
        freeNotice.setTextIsSelectable(true);
        aboutCard.addView(freeNotice);

        Button call = ui.button(local("الاتصال بالرقم", "Call phone number", "Κλήση τηλεφώνου"), false);
        call.setOnClickListener(v -> openExternal("tel:00962788272988"));
        aboutCard.addView(call, ui.margins(-1, -2, 0, 10, 0, 0));

        Button privacyPolicy = ui.button(local("سياسة الخصوصية", "Privacy policy", "Πολιτικὴ ἀπορρήτου"), false);
        privacyPolicy.setOnClickListener(v -> openExternal(
                "https://maen1977.github.io/orthodox_prayers/privacy/"
        ));
        aboutCard.addView(privacyPolicy, ui.margins(-1, -2, 0, 7, 0, 0));
        add(page.root, aboutCard, 0, 10);

        TextView privacy = centered(local("لا إعلانات، لا تسجيل دخول، ولا تتبع. لا توجد مفاتيح خاصة داخل التطبيق.",
                "No ads, login, or tracking. No private keys are stored in the app.",
                "Χωρὶς διαφημίσεις, σύνδεση ἢ παρακολούθηση."), 13, ui.colors().secondaryText(), false);
        add(page.root, privacy, 0, 16);
        return page.scroll;
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
        Button button = ui.button(title, active);
        button.setEnabled(true);
        button.setAlpha(1f);
        button.setContentDescription(title + (active
                ? local(" — اللغة المحددة", " — selected language", " — ἐπιλεγμένη γλῶσσα")
                : ""));
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

    private void openExternal(String value) {
        try {
            host.activity().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(value)));
        } catch (Exception error) {
            Toast.makeText(host.activity(), local(
                    "تعذر فتح الرابط على هذا الجهاز",
                    "The link could not be opened on this device",
                    "Ὁ σύνδεσμος δὲν μπορεῖ νὰ ἀνοίξει"
            ), Toast.LENGTH_SHORT).show();
        }
    }

}
