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
        JSONObject day = data.today();
        JSONObject selection = day == null ? null : day.optJSONObject("liturgy_service_selection");
        LinearLayout card = ui.card();

        String date = day == null ? "" : day.optString("date_iso", day.optString("date", "")).trim();
        if (!date.isEmpty()) {
            card.addView(centered(date, 15, ui.colors().secondaryText(), false));
        }

        if (!data.isTodayCurrent()) {
            String status = data.isRefreshing()
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_loading_today_s_data_8457881d)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_unavailable);
            card.addView(ui.infoBadge(status), ui.margins(-1, -2, 0, 8, 0, 5));
            card.addView(centered(
                    local(com.orthodoxprayers.privateapp.R.string.ui_the_screen_will_update_automatically_after_downl_a93a7fcf),
                    14, ui.colors().secondaryText(), false
            ), ui.margins(-1, -2, 0, 6, 0, 4));
            if (!data.isRefreshing()) {
                Button retry = ui.button(local(
                        com.orthodoxprayers.privateapp.R.string.ui_retry_update_da94fa97
                ), true);
                retry.setOnClickListener(v -> host.refreshData());
                card.addView(retry, ui.margins(-1, -2, 0, 8, 0, 0));
            }
            add(root, card, 14, 16);
            return;
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
        if (displayable) {
            Button open = ui.button(localFormat(
                    com.orthodoxprayers.privateapp.R.string.ui_open_full_appointed_liturgy_format,
                    title
            ), true);
            open.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
            card.addView(open, ui.margins(-1, -2, 0, 10, 0, 0));
        } else {
            card.addView(ui.badge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_complete_service_not_available_without_fallback
            ), false), ui.margins(-1, -2, 0, 10, 0, 0));
        }
        add(root, card, 14, 16);
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 7, 0, 0));
    }
}
