package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.data.TranslationCoverage;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

public final class LanguagePacksScreen extends BaseScreen {
    public LanguagePacksScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("اللغات النشطة", "Active languages", "Ἐνεργὲς γλῶσσες"), true);
        add(page.root, ui.infoBadge(local(
                "النصوص الأساسية للغات الثلاث مضمّنة وتعمل دون إنترنت. اختر اللغات التي تريد إظهارها في محدد اللغة. لا يستطيع التطبيق حذف ملفات من APK بعد التثبيت.",
                "Base texts for all three languages are embedded and work offline. Choose which languages appear in the language selector. The app cannot remove files from an installed APK.",
                "Τὰ βασικὰ κείμενα καὶ τῶν τριῶν γλωσσῶν εἶναι ἐνσωματωμένα. Ἐπίλεξε ποιες γλῶσσες θὰ φαίνονται στὸν ἐπιλογέα."
        )), 10, 10);
        addPack(page.root, "ar", "العربية");
        addPack(page.root, "en", "English");
        addPack(page.root, "el", "Ελληνικά");
        return page.scroll;
    }

    private void addPack(LinearLayout root, String language, String title) {
        TranslationCoverage.Result coverage = data.translationCoverage(language);
        LinearLayout card = ui.card();
        TextView heading = ui.text(title + " — " + coverage.percent + "%", 18, ui.colors().primaryText(), true);
        card.addView(heading);
        boolean enabled = preferences.offlineLanguageEnabled(language);
        boolean selected = language.equals(preferences.effectiveLanguage());
        Button toggle = ui.button(selected
                ? local("اللغة المستخدمة الآن", "Currently selected", "Τρέχουσα γλῶσσα")
                : enabled
                    ? local("إخفاؤها من محدد اللغة", "Hide from language selector", "Ἀπόκρυψη ἀπὸ τὸν ἐπιλογέα")
                    : local("إظهارها في محدد اللغة", "Show in language selector", "Ἐμφάνιση στὸν ἐπιλογέα"), enabled);
        toggle.setEnabled(!selected);
        toggle.setAlpha(selected ? 0.7f : 1f);
        toggle.setOnClickListener(v -> {
            preferences.setOfflineLanguageEnabled(language, !enabled);
            host.navigate("language_packs", null);
        });
        card.addView(toggle, ui.margins(-1, -2, 0, 8, 0, 0));
        add(root, card, 2, 8);
    }
}
