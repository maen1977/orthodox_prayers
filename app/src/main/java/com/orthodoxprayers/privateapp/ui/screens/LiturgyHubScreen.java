package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

/** Stable, always-useful destination for today's rite and the stored service books. */
public final class LiturgyHubScreen extends BaseScreen {
    private static final String[] ADJACENT_SERVICE_IDS = {
            "proskomide",
            "orthros",
            "first_hour",
            "third_hour",
            "sixth_hour",
            "ninth_hour",
            "pre_communion_prayers",
            "thanksgiving_after_communion"
    };

    public LiturgyHubScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_cdfaf7bd), false);
        page.root.addView(ui.sectionTitle(local(
                com.orthodoxprayers.privateapp.R.string.ui_appointed_liturgy_label
        )));
        addAppointedLiturgy(page.root);
        addStoredLiturgy(page.root);
        addAdjacentServices(page.root);
        return page.scroll;
    }

    private void addAppointedLiturgy(LinearLayout root) {
        JSONObject day = data.today();
        JSONObject selection = day == null ? null : day.optJSONObject("liturgy_service_selection");
        LinearLayout card = ui.card();

        if (day != null) {
            String date = day.optString("date_iso", day.optString("date", "")).trim();
            if (!date.isEmpty()) {
                TextView dateView = centered(date, 15, ui.colors().secondaryText(), false);
                card.addView(dateView, ui.margins(-1, -2, 0, 0, 0, 10));
            }
        }

        if (!data.isTodayCurrent()) {
            String status = data.isRefreshing()
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_loading_today_s_data_8457881d)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_unavailable);
            card.addView(ui.infoBadge(status), ui.margins(-1, -2, 0, 4, 0, 4));
            card.addView(centered(
                    local(com.orthodoxprayers.privateapp.R.string.ui_the_screen_will_update_automatically_after_downl_a93a7fcf),
                    14, ui.colors().secondaryText(), false
            ), ui.margins(-1, -2, 0, 8, 0, 4));
            if (!data.isRefreshing()) {
                Button retry = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_retry_update_da94fa97), true);
                retry.setOnClickListener(v -> host.refreshData());
                card.addView(retry, ui.margins(-1, -2, 0, 8, 0, 0));
            }
            add(root, card, 8, 16);
            return;
        }

        if (selection == null) {
            card.addView(ui.infoBadge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_no_trusted_details_for_this_date_are_included_in_dfb3006c
            )), ui.margins(-1, -2, 0, 4, 0, 4));
            add(root, card, 8, 16);
            return;
        }

        String title = localized(selection.optJSONObject("label"), "");
        String form = localized(selection.optJSONObject("service_form_label"), "");
        String availability = localized(selection.optJSONObject("availability_note"), "");

        if (!title.isEmpty()) {
            TextView titleView = centered(title, 21, ui.colors().primaryText(), true);
            card.addView(titleView, ui.margins(-1, -2, 0, 2, 0, 10));
        }
        addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_service_form_label), form);
        if (!availability.isEmpty()) {
            card.addView(ui.infoBadge(availability), ui.margins(-1, -2, 0, 8, 0, 8));
        }

        String type = selection.optString("service_type", "").trim();
        boolean displayable = selection.optBoolean("displayable", false)
                && !"no_divine_liturgy".equals(type)
                && !"typikon_override_required".equals(type);
        if (displayable) {
            String label = title.isEmpty()
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_open_complete_service_beginning_to_end)
                    : localFormat(com.orthodoxprayers.privateapp.R.string.ui_open_full_appointed_liturgy_format, title);
            Button open = ui.button(label, true);
            open.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
            card.addView(open, ui.margins(-1, -2, 0, 8, 0, 0));
        } else {
            card.addView(ui.badge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_complete_service_not_available_without_fallback
            ), false), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        add(root, card, 8, 16);
    }

    private void addStoredLiturgy(LinearLayout root) {
        root.addView(ui.sectionTitle(local(
                com.orthodoxprayers.privateapp.R.string.ui_complete_liturgy_library
        )));
        JSONObject service = data.findService("library::divine_liturgy");
        if (service == null) return;
        String title = localized(service.optJSONObject("title"), local(
                com.orthodoxprayers.privateapp.R.string.ui_shortcut_divine_liturgy_r43
        ));
        LinearLayout card = ui.actionCard(
                com.orthodoxprayers.privateapp.R.drawable.ic_action_liturgy,
                title,
                local(com.orthodoxprayers.privateapp.R.string.ui_full_liturgy_library_hint)
        );
        card.setOnClickListener(v -> host.navigate("reader", "library::divine_liturgy"));
        add(root, card, 2, 10);
    }

    private void addAdjacentServices(LinearLayout root) {
        root.addView(ui.sectionTitle(local(
                com.orthodoxprayers.privateapp.R.string.ui_liturgy_preparation_and_adjacent_services
        )));
        for (String serviceId : ADJACENT_SERVICE_IDS) {
            JSONObject service = data.findService("library::" + serviceId);
            if (service == null) continue;
            String title = localized(service.optJSONObject("title"), serviceId);
            LinearLayout card = ui.actionCard(
                    com.orthodoxprayers.privateapp.R.drawable.ic_action_prayers,
                    title,
                    local(com.orthodoxprayers.privateapp.R.string.ui_open_complete_service_beginning_to_end)
            );
            card.setOnClickListener(v -> host.navigate("reader", "library::" + serviceId));
            add(root, card, 2, 8);
        }
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 7, 0, 0));
    }
}
