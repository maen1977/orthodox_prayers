package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.view.View;
import android.widget.Button;
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
        String title = localized(reading.optJSONObject("title"), local("قراءة", "Reading", "Ἀνάγνωσμα"));
        UiKit.Page page = page(title, true);
        LinearLayout card = ui.card();
        String referenceText = localized(reading.optJSONObject("reference"), "").trim();
        if (!referenceText.isEmpty()) {
            TextView reference = centered(referenceText, 19, ui.colors().accentText(), true);
            card.addView(reference);
        }
        LocalizedValue value = data.localizedValue(reading.optJSONObject("body"), "");
        String exactText = value.text == null ? "" : value.text.trim();
        TextView body = ui.body(exactText.isEmpty() ? unavailableMessage() : value.text, false);
        body.setPadding(0, ui.dp(12), 0, ui.dp(8));
        card.addView(body);
        if (value.translationUnavailable || exactText.isEmpty()) card.addView(ui.badge(unavailableBadge(), false));
        JSONObject nativeVerification = reading.optJSONObject("native_source_verification");
        JSONObject languageVerification = nativeVerification == null ? null : nativeVerification.optJSONObject(preferences.effectiveLanguage());
        String nativeStatus = languageVerification == null ? "" : languageVerification.optString("status", "");
        if (reading.optBoolean("translation_locked", false)
                && ("VERIFIED_EXACT_NATIVE_SOURCE".equals(nativeStatus)
                        || "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(nativeStatus)
                        || "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS".equals(nativeStatus))) {
            card.addView(ui.badge(local("نص كتابي أصلي موثّق من مصدر مستقل، بلا ترجمة أو تشكيل آلي", "Verified native Scripture from an independent source; no translation or automatic marking", "Ἐπαληθευμένο πρωτότυπο βιβλικὸ κείμενο ἀπὸ ἀνεξάρτητη πηγή, χωρὶς μετάφραση ἢ αὐτόματο τονισμό"), true), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        String source = localized(reading.optJSONObject("source"), "");
        if (!source.isEmpty()) card.addView(centered(source, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 8, 0, 0));

        JSONObject verification = reading.optJSONObject("native_source_verification");
        JSONObject lane = verification == null ? null : verification.optJSONObject(preferences.effectiveLanguage());
        String sourceId = lane == null ? "" : lane.optString("source_id", "").trim();
        String sourceUrl = lane == null ? "" : lane.optString("source_url", "").trim();
        if (!sourceId.isEmpty()) {
            card.addView(ui.text(local("المصدر المسجل: ", "Registered source: ", "Καταχωρισμένη πηγή: ") + data.sourceName(sourceId),
                    12, ui.colors().primaryText(), true), ui.margins(-1, -2, 0, 6, 0, 0));
        }
        if (sourceUrl.isEmpty() && !sourceId.isEmpty()) sourceUrl = data.sourceUrl(sourceId);
        if (!sourceUrl.isEmpty()) {
            final String url = sourceUrl;
            Button open = ui.smallButton(local("فتح مصدر القراءة", "Open reading source", "Ἄνοιγμα πηγῆς ἀναγνώσματος"), false);
            open.setOnClickListener(v -> {
                try { host.activity().startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))); }
                catch (Exception ignored) { }
            });
            card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
        }
        Button allSources = ui.smallButton(local("جميع المصادر والمراجع", "All sources and references", "Ὅλες οἱ πηγές"), false);
        allSources.setOnClickListener(v -> host.navigate("sources", null));
        card.addView(allSources, ui.margins(-1, -2, 0, 5, 0, 0));
        add(page.root, card, 12, 16);
        return page.scroll;
    }

    private String unavailableMessage() {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
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

    private String unavailableBadge() {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
            return local("البروكيمنن غير متوفر من مصدر موثّق", "Verified Prokeimenon unavailable", "Μὴ διαθέσιμο ἐπαληθευμένο Προκείμενον");
        }
        return local("النص الكتابي الأصلي غير متوفر لهذا المقطع", "Native Scripture text unavailable for this passage", "Τὸ πρωτότυπο βιβλικὸ κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ ἀνάγνωσμα");
    }
}
