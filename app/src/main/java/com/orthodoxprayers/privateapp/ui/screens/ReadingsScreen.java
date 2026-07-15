package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class ReadingsScreen extends BaseScreen {
    public ReadingsScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("قراءات اليوم", "Today's Readings", "Ἀναγνώσματα Ἡμέρας"), true);
        TextView source = centered(localized(data.today().optJSONObject("source_note"), ""), 13, ui.colors().secondaryText(), false);
        add(page.root, source, 12, 8);
        JSONArray readings = data.today().optJSONArray("readings");
        if (readings != null) {
            for (int i = 0; i < readings.length(); i++) {
                JSONObject reading = readings.optJSONObject(i);
                if (reading != null) add(page.root, readingCard(reading), 3, 9);
            }
        }
        return page.scroll;
    }

    private LinearLayout readingCard(JSONObject reading) {
        LinearLayout card = ui.card();
        String title = reading.optString("icon", "📖") + "  " + localized(reading.optJSONObject("title"), local("قراءة", "Reading", "Ἀνάγνωσμα"));
        TextView heading = ui.text(title, 20, ui.colors().primaryText(), true);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) heading.setAccessibilityHeading(true);
        card.addView(heading);
        String reference = localized(reading.optJSONObject("reference"), "").trim();
        if (!reference.isEmpty()) {
            card.addView(ui.text(reference, 15, ui.colors().accentText(), true), ui.margins(-1, -2, 0, 4, 0, 0));
        }
        LocalizedValue value = data.localizedValue(reading.optJSONObject("body"), "");
        String exactText = value.text == null ? "" : value.text.trim();
        String displayText = exactText.isEmpty() ? unavailableMessage(reading) : value.text;
        TextView preview = ui.body(trim(displayText, 320), false);
        preview.setMaxLines(8);
        card.addView(preview, ui.margins(-1, -2, 0, 6, 0, 0));
        JSONObject nativeVerification = reading.optJSONObject("native_source_verification");
        JSONObject languageVerification = nativeVerification == null ? null : nativeVerification.optJSONObject(preferences.effectiveLanguage());
        String nativeStatus = languageVerification == null ? "" : languageVerification.optString("status", "");
        if (reading.optBoolean("translation_locked", false)
                && ("VERIFIED_EXACT_NATIVE_SOURCE".equals(nativeStatus)
                        || "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(nativeStatus)
                        || "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS".equals(nativeStatus))) {
            card.addView(ui.badge(local("نص كتابي أصلي موثّق من مصدر مستقل، بلا ترجمة أو تشكيل آلي", "Verified native Scripture from an independent source; no translation or automatic marking", "Ἐπαληθευμένο πρωτότυπο βιβλικὸ κείμενο ἀπὸ ἀνεξάρτητη πηγή, χωρὶς μετάφραση ἢ αὐτόματο τονισμό"), true), ui.margins(-1, -2, 0, 6, 0, 4));
        }
        if (value.translationUnavailable || exactText.isEmpty()) {
            card.addView(ui.badge(unavailableBadge(reading), false), ui.margins(-1, -2, 0, 4, 0, 4));
        }
        Button open = ui.smallButton(local("فتح القراءة كاملة", "Open full reading", "Ἄνοιγμα ἀναγνώσματος"), false);
        open.setOnClickListener(v -> host.openReading(reading));
        card.addView(open, ui.margins(-1, -2, 0, 6, 0, 0));
        return card;
    }

    private String unavailableMessage(JSONObject reading) {
        String kind = reading.optString("kind", "");
        if ("prokeimenon".equals(kind)) {
            return local(
                    "لم يتوفر نص بروكيمنن موثّق لهذا اليوم؛ لن يعرض التطبيق نصًا مخمّنًا.",
                    "A verified Prokeimenon is not available for this day; the app will not display a guessed text.",
                    "Δὲν εἶναι διαθέσιμο ἐπαληθευμένο Προκείμενον γιὰ αὐτὴν τὴν ἡμέρα· ἡ ἐφαρμογὴ δὲν θὰ δείξει εἰκαζόμενο κείμενο."
            );
        }
        return local(
                "تعذّر توفير النص الكتابي الموثّق لهذا المقطع. بقيت آخر بيانات سليمة محفوظة.",
                "Verified Scripture text is unavailable for this passage. The last valid data remains saved.",
                "Τὸ ἐπαληθευμένο βιβλικὸ κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ ἀνάγνωσμα. Διατηροῦνται τὰ τελευταῖα ἔγκυρα δεδομένα."
        );
    }

    private String unavailableBadge(JSONObject reading) {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
            return local("البروكيمنن غير متوفر من مصدر موثّق", "Verified Prokeimenon unavailable", "Μὴ διαθέσιμο ἐπαληθευμένο Προκείμενον");
        }
        return local("النص الكتابي الأصلي غير متوفر لهذا المقطع", "Native Scripture text unavailable for this passage", "Τὸ πρωτότυπο βιβλικὸ κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ ἀνάγνωσμα");
    }

    private static String trim(String value, int max) {
        if (value == null || value.length() <= max) return value == null ? "" : value;
        return value.substring(0, max).trim() + "…";
    }
}
