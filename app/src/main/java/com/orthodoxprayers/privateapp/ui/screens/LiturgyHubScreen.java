package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

/**
 * Stable top-level Liturgy destination.
 *
 * The tab itself is never hidden by liturgical availability. The embedded
 * calendar decides which Liturgy is appointed; only the reader action is
 * enabled when that exact native edition is displayable. This keeps the
 * navigation stable while preserving the fail-closed no-wrong-rite policy.
 */
public final class LiturgyHubScreen extends BaseScreen {
    public LiturgyHubScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_cdfaf7bd), false);
        JSONObject day = data.today();
        JSONObject selection = day == null ? null : day.optJSONObject("liturgy_service_selection");

        LinearLayout card = ui.card();
        if (day != null) {
            String date = day.optString("date_iso", "").trim();
            if (!date.isEmpty()) {
                TextView dateView = centered(date, 15, ui.colors().secondaryText(), false);
                card.addView(dateView, ui.margins(-1, -2, 0, 0, 0, 10));
            }
        }

        if (selection == null) {
            card.addView(ui.infoBadge(local(
                    com.orthodoxprayers.privateapp.R.string.ui_no_trusted_details_for_this_date_are_included_in_dfb3006c
            )), ui.margins(-1, -2, 0, 4, 0, 4));
            add(page.root, card, 14, 16);
            return page.scroll;
        }

        String title = localized(selection.optJSONObject("label"), "");
        String form = localized(selection.optJSONObject("service_form_label"), "");
        String availability = localized(selection.optJSONObject("availability_note"), "");

        if (!title.isEmpty()) {
            TextView titleView = centered(title, 21, ui.colors().primaryText(), true);
            card.addView(titleView, ui.margins(-1, -2, 0, 2, 0, 10));
        }
        addField(card,
                local(com.orthodoxprayers.privateapp.R.string.ui_appointed_liturgy_label),
                title);
        addField(card,
                local(com.orthodoxprayers.privateapp.R.string.ui_service_form_label),
                form);
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
        }

        add(page.root, card, 14, 16);
        return page.scroll;
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        TextView text = ui.text(label + ":\n" + value, 15, ui.colors().secondaryText(), false);
        card.addView(text, ui.margins(-1, -2, 0, 7, 0, 0));
    }
}
