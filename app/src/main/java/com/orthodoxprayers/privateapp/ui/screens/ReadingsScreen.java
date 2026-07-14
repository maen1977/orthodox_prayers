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
        String reference = localized(reading.optJSONObject("reference"), "");
        card.addView(ui.text(reference, 15, ui.colors().accentText(), true), ui.margins(-1, -2, 0, 4, 0, 0));
        LocalizedValue value = data.localizedValue(reading.optJSONObject("body"), "");
        TextView preview = ui.body(trim(value.text, 320), false);
        preview.setMaxLines(8);
        card.addView(preview, ui.margins(-1, -2, 0, 6, 0, 0));
        JSONObject nativeVerification = reading.optJSONObject("native_source_verification");
        JSONObject languageVerification = nativeVerification == null ? null : nativeVerification.optJSONObject(preferences.effectiveLanguage());
        String nativeStatus = languageVerification == null ? "" : languageVerification.optString("status", "");
        if (reading.optBoolean("translation_locked", false)
                && ("VERIFIED_EXACT_NATIVE_SOURCE".equals(nativeStatus) || "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(nativeStatus))) {
            card.addView(ui.badge(local("نص كتابي أصلي مقفل أمام الترجمة أو التشكيل الآلي", "Verified native Scripture text; translation and automatic marking are blocked", "Ἐπαληθευμένο πρωτότυπο βιβλικὸ κείμενο"), true), ui.margins(-1, -2, 0, 6, 0, 4));
        }
        if (value.translationUnavailable) {
            card.addView(ui.badge(local("النص الأصلي المعتمد بهذه اللغة غير متوفر لهذا المقطع", "Official native text unavailable for this section", "Τὸ ἐπίσημο πρωτότυπο κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ τμήμα"), false), ui.margins(-1, -2, 0, 4, 0, 4));
        }
        Button open = ui.smallButton(local("فتح القراءة كاملة", "Open full reading", "Ἄνοιγμα ἀναγνώσματος"), false);
        open.setOnClickListener(v -> host.openReading(reading));
        card.addView(open, ui.margins(-1, -2, 0, 6, 0, 0));
        return card;
    }

    private static String trim(String value, int max) {
        if (value == null || value.length() <= max) return value == null ? "" : value;
        return value.substring(0, max).trim() + "…";
    }
}
