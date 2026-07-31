package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class UpcomingScreen extends BaseScreen {
    public UpcomingScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_upcoming_days_a15c452f), true);
        TextView note = centered(local(com.orthodoxprayers.privateapp.R.string.ui_the_signed_package_keeps_today_and_the_next_seve_8ba1a6f0), 13, ui.colors().secondaryText(), false);
        add(page.root, note, 12, 8);
        JSONArray upcoming = data.rollingWeekDays();
        if (upcoming.length() == 0) upcoming = data.today().optJSONArray("upcoming");
        if (upcoming != null) {
            for (int i = 0; i < upcoming.length(); i++) {
                JSONObject item = upcoming.optJSONObject(i);
                if (item == null) continue;
                add(page.root, dayCard(item), 2, 7);
            }
        }
        JSONObject todayFasting = data.today().optJSONObject("fasting");
        JSONObject guidance = isFastingDay(todayFasting) ? todayFasting.optJSONObject("guidance") : null;
        if (guidance != null) {
            LinearLayout reminder = ui.card();
            String spiritual = localized(guidance.optJSONObject("spiritual_note"), "");
            String health = localized(guidance.optJSONObject("health_note"), "");
            if (!spiritual.isEmpty()) reminder.addView(ui.text(spiritual, 13, ui.colors().secondaryText(), false));
            if (!health.isEmpty()) reminder.addView(ui.text(health, 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 6, 0, 0));
            add(page.root, reminder, 8, 16);
        }
        return page.scroll;
    }

    private LinearLayout dayCard(JSONObject item) {
        LinearLayout card = ui.card();
        String itemDate = item.optString("date_iso", item.optString("date", ""));
        String day = localized(item.optJSONObject("day"), localized(item.optJSONObject("date_label"), itemDate));
        TextView heading = ui.text(day, 16, ui.colors().primaryText(), true);
        card.addView(heading);
        JSONObject fasting = item.optJSONObject("fasting");
        card.addView(ui.text(fastingDisplayTitle(item, itemDate), 14, ui.colors().accentText(), true), ui.margins(-1, -2, 0, 4, 0, 0));
        if (isFastingDay(fasting)) {
            addCompactFastingItems(card, fasting);
            addFastingGuide(card, fasting, false);
        }
        String feast = displayableCommemoration(item);
        if (!feast.isEmpty()) card.addView(ui.text(feast, 13, ui.colors().secondaryText(), false));
        addAppointedLiturgy(card, item, itemDate);
        JSONObject refs = item.optJSONObject("reading_references");
        addReference(card, refs, "epistle", local(com.orthodoxprayers.privateapp.R.string.ui_epistle_dd82c199));
        addReference(card, refs, "gospel", local(com.orthodoxprayers.privateapp.R.string.ui_gospel_68845cc5));
        card.setContentDescription(day + ". " + feast);
        if (!itemDate.isEmpty()) {
            card.setClickable(true);
            card.setFocusable(true);
            card.setOnClickListener(v -> host.navigate("calendar_day", itemDate));
        }
        return card;
    }

    private void addAppointedLiturgy(LinearLayout card, JSONObject item, String itemDate) {
        JSONObject selection = item.optJSONObject("liturgy_service_selection");
        if (selection == null) return;
        String liturgy = localized(selection.optJSONObject("label"), "");
        String form = localized(selection.optJSONObject("service_form_label"), "");
        if (!liturgy.isEmpty()) {
            card.addView(ui.text(
                    local(com.orthodoxprayers.privateapp.R.string.ui_appointed_liturgy_label) + ": " + liturgy,
                    14,
                    ui.colors().primaryText(),
                    true
            ), ui.margins(-1, -2, 0, 7, 0, 0));
        }
        if (!form.isEmpty()) {
            card.addView(ui.text(
                    local(com.orthodoxprayers.privateapp.R.string.ui_service_form_label) + ": " + form,
                    13,
                    ui.colors().secondaryText(),
                    false
            ));
        }
        JSONObject service = findService(item.optJSONArray("services"), "divine_liturgy");
        boolean complete = service != null && service.optBoolean("full_service_complete", false);
        if (complete && !itemDate.isEmpty()) {
            android.widget.Button open = ui.smallButton(
                    local(com.orthodoxprayers.privateapp.R.string.ui_open_complete_service_beginning_to_end),
                    true
            );
            open.setOnClickListener(v -> host.navigate(
                    "reader",
                    com.orthodoxprayers.privateapp.data.DataRepository.datedServiceId(itemDate, "divine_liturgy")
            ));
            card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
        } else {
            String note = localized(selection.optJSONObject("availability_note"), "");
            if (note.isEmpty()) {
                note = local(com.orthodoxprayers.privateapp.R.string.ui_complete_service_not_available_without_fallback);
            }
            card.addView(ui.badge(note, false), ui.margins(-1, -2, 0, 7, 0, 0));
        }
    }

    private JSONObject findService(JSONArray services, String id) {
        if (services == null) return null;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service != null && id.equals(service.optString("id", ""))) return service;
        }
        return null;
    }

    private void addReference(LinearLayout card, JSONObject refs, String kind, String prefix) {
        if (refs == null) return;
        JSONObject item = refs.optJSONObject(kind);
        if (item == null) return;
        String reference = localized(item.optJSONObject("reference"), "");
        if (!reference.isEmpty()) card.addView(ui.text(prefix + reference, 12, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
    }
}
