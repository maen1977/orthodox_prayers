package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

/** One clear entry point: the complete appointed Liturgy for the current church day. */
public final class LiturgyHubScreen extends BaseScreen {
    public LiturgyHubScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(
                com.orthodoxprayers.privateapp.R.string.ui_liturgy_cdfaf7bd
        ), false);
        addTodayLiturgy(page.root);
        return page.scroll;
    }

    private void addTodayLiturgy(LinearLayout root) {
        // today.json may be an older signed snapshot while the annual calendar
        // already contains the current date and its appointed Liturgy.
        JSONObject day = data.currentDayForDisplay();
        JSONObject selection = day == null ? null : day.optJSONObject("liturgy_service_selection");
        LinearLayout card = ui.card();

        String date = day == null ? "" : day.optString("date_iso", day.optString("date", "")).trim();
        if (!date.isEmpty()) {
            card.addView(centered(date, 15, ui.colors().secondaryText(), false));
        }

        if (selection == null) {
            card.addView(ui.infoBadge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_no_trusted_details_for_this_date_are_included_in_dfb3006c
            )));
            add(root, card, 14, 16);
            return;
        }

        String title = localized(selection.optJSONObject("label"), local(
                com.orthodoxprayers.privateapp.R.string.ui_appointed_liturgy_label
        ));
        card.addView(centered(title, 22, ui.colors().primaryText(), true),
                ui.margins(-1, -2, 0, 8, 0, 10));

        addField(card,
                local(com.orthodoxprayers.privateapp.R.string.ui_today_s_commemoration_af76eeaa),
                localized(day.optJSONObject("feast"), ""));
        addField(card,
                local(com.orthodoxprayers.privateapp.R.string.ui_today_s_fasting_aa40c904),
                fastingDisplayTitle(day, date));
        addField(card,
                local(com.orthodoxprayers.privateapp.R.string.ui_service_form_label),
                localized(selection.optJSONObject("service_form_label"), ""));

        String availability = localized(selection.optJSONObject("availability_note"), "");
        if (!availability.isEmpty()) {
            card.addView(ui.infoBadge(availability), ui.margins(-1, -2, 0, 9, 0, 6));
        }

        String type = selection.optString("service_type", "").trim();
        boolean displayable = selection.optBoolean("displayable", false)
                && !"no_divine_liturgy".equals(type)
                && !"typikon_override_required".equals(type);
        if (!data.isTodayCurrent()) {
            card.addView(ui.infoBadge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_unavailable
            )), ui.margins(-1, -2, 0, 8, 0, 5));
        }
        if (displayable) {
            Button open = ui.button(localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_open_full_appointed_liturgy_format,
                    title
            ), true);
            String appointedId = appointedServiceId(selection);
            open.setOnClickListener(v -> {
                if ("divine_liturgy".equals(appointedId)) {
                    host.navigate("reader", "divine_liturgy");
                } else {
                    host.navigate("reader", appointedId);
                }
            });
            card.addView(open, ui.margins(-1, -2, 0, 10, 0, 0));
        } else {
            card.addView(ui.badge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_complete_service_not_available_without_fallback
            ), false), ui.margins(-1, -2, 0, 10, 0, 0));
        }
        add(root, card, 14, 16);
    }

    private String appointedServiceId(JSONObject selection) {
        String explicit = selection == null ? "" : selection.optString("service_id", "").trim();
        if (!explicit.isEmpty()) return explicit;
        String type = selection == null ? "" : selection.optString("service_type", "").trim();
        if ("basil".equals(type)) return "divine_liturgy_basil";
        if ("presanctified".equals(type)) return "presanctified_liturgy";
        return "divine_liturgy";
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 7, 0, 0));
    }
}
