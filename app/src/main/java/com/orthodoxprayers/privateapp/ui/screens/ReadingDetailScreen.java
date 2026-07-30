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
        String title = localized(reading.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_reading_6e6a82ce));
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
            card.addView(ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_verified_native_scripture_from_an_independent_so_a8f7898c), true), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        String source = localized(reading.optJSONObject("source"), "");
        if (!source.isEmpty()) card.addView(centered(source, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 8, 0, 0));

        JSONObject verification = reading.optJSONObject("native_source_verification");
        JSONObject lane = verification == null ? null : verification.optJSONObject(preferences.effectiveLanguage());
        String sourceId = lane == null ? "" : lane.optString("source_id", "").trim();
        String sourceUrl = lane == null ? "" : lane.optString("source_url", "").trim();
        if (!sourceId.isEmpty()) {
            card.addView(ui.text(local(com.orthodoxprayers.privateapp.R.string.ui_registered_source_b7f2bf22) + data.sourceName(sourceId),
                    12, ui.colors().primaryText(), true), ui.margins(-1, -2, 0, 6, 0, 0));
        }
        if (sourceUrl.isEmpty() && !sourceId.isEmpty()) sourceUrl = data.sourceUrl(sourceId);
        if (!sourceUrl.isEmpty()) {
            final String url = sourceUrl;
            Button open = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_open_reading_source_0dc31b35), false);
            open.setOnClickListener(v -> {
                try { host.activity().startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url))); }
                catch (Exception ignored) { }
            });
            card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
        }
        Button allSources = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_all_sources_and_references_5cebd827), false);
        allSources.setOnClickListener(v -> host.navigate("sources", null));
        card.addView(allSources, ui.margins(-1, -2, 0, 5, 0, 0));
        add(page.root, card, 12, 16);
        return page.scroll;
    }

    private String unavailableMessage() {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_a_verified_prokeimenon_is_not_available_for_this_61c99c08);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_verified_scripture_text_is_unavailable_for_this__1624033a);
    }

    private String unavailableBadge() {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_verified_prokeimenon_unavailable_9ac3fd2f);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_native_scripture_text_unavailable_for_this_passa_80766f8b);
    }
}
