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
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_today_s_readings_3cf1dbd5), true);
        if (!data.isTodayCurrent()) {
            TextView blocked = centered(
                    data.isRefreshing()
                            ? local(com.orthodoxprayers.privateapp.R.string.ui_loading_today_s_data_8457881d)
                            : local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_unavailable),
                    15, ui.colors().primaryText(), true
            );
            add(page.root, blocked, 18, 10);
            TextView detail = centered(
                    local(com.orthodoxprayers.privateapp.R.string.ui_the_screen_will_update_automatically_after_downl_a93a7fcf),
                    14, ui.colors().secondaryText(), false
            );
            add(page.root, detail, 2, 10);
            if (!data.isRefreshing()) {
                Button refresh = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_retry_update_da94fa97), true);
                refresh.setOnClickListener(v -> host.refreshData());
                add(page.root, refresh, 2, 12);
            }
            return page.scroll;
        }
        TextView source = centered(localized(data.today().optJSONObject("source_note"), ""), 13, ui.colors().secondaryText(), false);
        add(page.root, source, 12, 8);
        JSONArray readings = data.currentReadings();
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
        String title = localized(reading.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_reading_6e6a82ce));
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
            card.addView(ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_verified_native_scripture_from_an_independent_so_a8f7898c), true), ui.margins(-1, -2, 0, 6, 0, 4));
        }
        if (value.translationUnavailable || exactText.isEmpty()) {
            card.addView(ui.badge(unavailableBadge(reading), false), ui.margins(-1, -2, 0, 4, 0, 4));
        }
        Button open = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_open_full_reading_a1308e52), false);
        open.setOnClickListener(v -> host.openReading(reading));
        card.addView(open, ui.margins(-1, -2, 0, 6, 0, 0));
        return card;
    }

    private String unavailableMessage(JSONObject reading) {
        String kind = reading.optString("kind", "");
        if ("prokeimenon".equals(kind)) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_a_verified_prokeimenon_is_not_available_for_this_61c99c08);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_verified_scripture_text_is_unavailable_for_this__1624033a);
    }

    private String unavailableBadge(JSONObject reading) {
        if ("prokeimenon".equals(reading.optString("kind", ""))) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_verified_prokeimenon_unavailable_9ac3fd2f);
        }
        return local(com.orthodoxprayers.privateapp.R.string.ui_native_scripture_text_unavailable_for_this_passa_80766f8b);
    }

    private static String trim(String value, int max) {
        if (value == null || value.length() <= max) return value == null ? "" : value;
        return value.substring(0, max).trim() + "…";
    }
}
