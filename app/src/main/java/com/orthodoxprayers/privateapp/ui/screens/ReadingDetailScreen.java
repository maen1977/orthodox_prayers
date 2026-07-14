package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

public final class ReadingDetailScreen extends BaseScreen {
    private final JSONObject reading;

    public ReadingDetailScreen(ScreenHost host, JSONObject reading) {
        super(host);
        this.reading = reading == null ? new JSONObject() : reading;
    }

    @Override
    public View createView() {
        String title = reading.optString("icon", "📖") + "  " + localized(reading.optJSONObject("title"), local("قراءة", "Reading", "Ἀνάγνωσμα"));
        UiKit.Page page = page(title, true);
        LinearLayout card = ui.card();
        TextView reference = centered(localized(reading.optJSONObject("reference"), ""), 19, ui.colors().accentText(), true);
        card.addView(reference);
        LocalizedValue value = data.localizedValue(reading.optJSONObject("body"), "");
        TextView body = ui.body(value.text, false);
        body.setPadding(0, ui.dp(12), 0, ui.dp(8));
        card.addView(body);
        if (value.translationUnavailable) card.addView(ui.badge(local("النص الأصلي المعتمد بهذه اللغة غير متوفر لهذا المقطع", "Official native text unavailable for this section", "Τὸ ἐπίσημο πρωτότυπο κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ τμήμα"), false));
        JSONObject nativeVerification = reading.optJSONObject("native_source_verification");
        JSONObject languageVerification = nativeVerification == null ? null : nativeVerification.optJSONObject(preferences.effectiveLanguage());
        String nativeStatus = languageVerification == null ? "" : languageVerification.optString("status", "");
        if (reading.optBoolean("translation_locked", false)
                && ("VERIFIED_EXACT_NATIVE_SOURCE".equals(nativeStatus) || "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(nativeStatus))) {
            card.addView(ui.badge(local("نص كتابي أصلي من مصدره اللغوي المعتمد، بلا ترجمة أو تشكيل آلي", "Exact native-source Scripture text; no translation or automatic marking", "Ἀκριβὲς βιβλικὸ κείμενο τῆς ἐγκεκριμένης γλωσσικῆς πηγῆς"), true), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        String source = localized(reading.optJSONObject("source"), "");
        if (!source.isEmpty()) card.addView(centered(source, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 8, 0, 0));
        add(page.root, card, 12, 16);
        return page.scroll;
    }
}
