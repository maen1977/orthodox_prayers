package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class CalendarDayScreen extends BaseScreen {
    private final String date;
    public CalendarDayScreen(ScreenHost host, String date) { super(host); this.date = date == null ? "" : date; }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_day_details_37b21832), true);
        JSONObject item = findDay();
        if (item == null) {
            add(page.root, centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_trusted_details_for_this_date_are_included_in_dfb3006c), 16, ui.colors().secondaryText(), false), 30, 30);
            return page.scroll;
        }
        LinearLayout card = ui.card();
        card.addView(centered(date, 21, ui.colors().primaryText(), true));
        addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_old_calendar_date_02f8092d), localized(item.optJSONObject("julian_label"), item.optString("julian_date", "")));
        addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_commemoration_399506fc), localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), "")));
        addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_fasting_f1b1605d), localized(item.optJSONObject("status"), localized(item.optJSONObject("fast"), "")));
        addFastingGuide(card, item.optJSONObject("fasting"), true);
        JSONObject sunday = item.optJSONObject("sunday");
        if (sunday != null) {
            addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_sunday_cycle_a83925a1), localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_sunday_cycle_detail_format,
                    sunday.optInt("sunday_after_pentecost"),
                    sunday.optInt("resurrection_tone"),
                    sunday.optInt("eothinon")
            ));
        }
        JSONObject refs = item.optJSONObject("reading_references");
        if (refs != null) {
            addReference(card, refs.optJSONObject("matins_gospel"), local(com.orthodoxprayers.privateapp.R.string.ui_matins_gospel_995b30a1));
            addReference(card, refs.optJSONObject("epistle"), local(com.orthodoxprayers.privateapp.R.string.ui_epistle_a17bc087));
            addReference(card, refs.optJSONObject("gospel"), local(com.orthodoxprayers.privateapp.R.string.ui_gospel_b7b033e7));
        } else {
            addFullReadingReferences(card, item.optJSONArray("readings"));
        }
        addServiceButtons(card, item);
        add(page.root, card, 14, 16);
        return page.scroll;
    }

    private void addReference(LinearLayout card, JSONObject reading, String label) {
        if (reading == null) return;
        addField(card, label, localized(reading.optJSONObject("reference"), ""));
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 8, 0, 0));
    }

    private void addFullReadingReferences(LinearLayout card, JSONArray readings) {
        if (readings == null) return;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null) continue;
            String kind = reading.optString("kind", "");
            String label;
            if ("epistle".equals(kind)) label = local(com.orthodoxprayers.privateapp.R.string.ui_epistle_a17bc087);
            else if ("gospel".equals(kind)) label = local(com.orthodoxprayers.privateapp.R.string.ui_gospel_b7b033e7);
            else if (kind.contains("matins")) label = local(com.orthodoxprayers.privateapp.R.string.ui_matins_gospel_995b30a1);
            else continue;
            addReference(card, reading, label);
        }
    }

    private void addServiceButtons(LinearLayout card, JSONObject day) {
        JSONArray services = day.optJSONArray("services");
        if (services == null || services.length() == 0) return;
        card.addView(ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_this_day_is_complete_inside_the_signed_package_2072d1f2)), ui.margins(-1, -2, 0, 8, 0, 8));
        addServiceButton(card, services, "divine_liturgy", local(com.orthodoxprayers.privateapp.R.string.ui_open_the_complete_divine_liturgy_14695677), true);
        addServiceButton(card, services, "orthros", local(com.orthodoxprayers.privateapp.R.string.ui_orthros_2aa869d2), false);
        addServiceButton(card, services, "vespers", local(com.orthodoxprayers.privateapp.R.string.ui_vespers_1daa5b5d), false);
        addServiceButton(card, services, "morning_prayer", local(com.orthodoxprayers.privateapp.R.string.ui_morning_prayers_cbf9758b), false);
        addServiceButton(card, services, "evening_prayer", local(com.orthodoxprayers.privateapp.R.string.ui_evening_prayers_23ddb1fe), false);
        addServiceButton(card, services, "small_compline", local(com.orthodoxprayers.privateapp.R.string.ui_small_compline_c17433a9), false);
    }

    private void addServiceButton(LinearLayout card, JSONArray services, String id, String label, boolean primary) {
        boolean exists = false;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service != null && id.equals(service.optString("id", ""))) { exists = true; break; }
        }
        if (!exists) return;
        Button button = ui.button(label, primary);
        button.setOnClickListener(v -> host.navigate("reader",
                com.orthodoxprayers.privateapp.data.DataRepository.datedServiceId(date, id)));
        card.addView(button, ui.margins(-1, -2, 0, 5, 0, 0));
    }

    private JSONObject findDay() {
        return data.calendarDay(date);
    }
}
