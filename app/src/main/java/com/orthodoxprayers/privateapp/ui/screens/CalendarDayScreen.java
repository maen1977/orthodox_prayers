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
        UiKit.Page page = page(local("تفاصيل اليوم", "Day details", "Λεπτομέρειες ἡμέρας"), true);
        JSONObject item = findDay();
        if (item == null) {
            add(page.root, centered(local("لا توجد تفاصيل موثوقة لهذا التاريخ داخل الحزمة الحالية.", "No trusted details for this date are included in the current package.", "Δὲν ὑπάρχουν ἔμπιστες λεπτομέρειες γιὰ αὐτὴν τὴν ἡμερομηνία."), 16, ui.colors().secondaryText(), false), 30, 30);
            return page.scroll;
        }
        LinearLayout card = ui.card();
        card.addView(centered("📅  " + date, 21, ui.colors().primaryText(), true));
        addField(card, local("التاريخ القديم", "Old-calendar date", "Ἡμερομηνία παλαιοῦ ἡμερολογίου"), localized(item.optJSONObject("julian_label"), item.optString("julian_date", "")));
        addField(card, local("التذكار", "Commemoration", "Μνήμη"), localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), "")));
        addField(card, local("الصيام", "Fasting", "Νηστεία"), localized(item.optJSONObject("status"), localized(item.optJSONObject("fast"), "")));
        addFastingGuide(card, item.optJSONObject("fasting"), true);
        JSONObject sunday = item.optJSONObject("sunday");
        if (sunday != null) {
            addField(card, local("ترتيب الأحد", "Sunday cycle", "Κύκλος Κυριακῆς"), local(
                    "الأحد " + sunday.optInt("sunday_after_pentecost") + " بعد العنصرة — اللحن " + sunday.optInt("resurrection_tone") + " — الإيوثينا " + sunday.optInt("eothinon"),
                    "Sunday " + sunday.optInt("sunday_after_pentecost") + " after Pentecost — Tone " + sunday.optInt("resurrection_tone") + " — Eothinon " + sunday.optInt("eothinon"),
                    "Κυριακὴ " + sunday.optInt("sunday_after_pentecost") + " μετὰ τὴν Πεντηκοστήν — Ἦχος " + sunday.optInt("resurrection_tone") + " — Ἑωθινὸν " + sunday.optInt("eothinon")
            ));
        }
        JSONObject refs = item.optJSONObject("reading_references");
        if (refs != null) {
            addReference(card, refs.optJSONObject("matins_gospel"), local("إنجيل السحر", "Matins Gospel", "Ἑωθινὸν Εὐαγγέλιον"));
            addReference(card, refs.optJSONObject("epistle"), local("الرسالة", "Epistle", "Ἀπόστολος"));
            addReference(card, refs.optJSONObject("gospel"), local("الإنجيل", "Gospel", "Εὐαγγέλιον"));
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
            if ("epistle".equals(kind)) label = local("الرسالة", "Epistle", "Ἀπόστολος");
            else if ("gospel".equals(kind)) label = local("الإنجيل", "Gospel", "Εὐαγγέλιον");
            else if (kind.contains("matins")) label = local("إنجيل السحر", "Matins Gospel", "Ἑωθινὸν Εὐαγγέλιον");
            else continue;
            addReference(card, reading, label);
        }
    }

    private void addServiceButtons(LinearLayout card, JSONObject day) {
        JSONArray services = day.optJSONArray("services");
        if (services == null || services.length() == 0) return;
        card.addView(ui.infoBadge(local(
                "هذا اليوم موجود كاملًا داخل الحزمة الموقعة.",
                "This day is complete inside the signed package.",
                "Αὐτὴ ἡ ἡμέρα περιέχεται πλήρης στὴν ὑπογεγραμμένη δέσμη."
        )), ui.margins(-1, -2, 0, 8, 0, 8));
        addServiceButton(card, services, "divine_liturgy", local("ابدأ متابعة القداس الكامل", "Open the complete Divine Liturgy", "Ἄνοιγμα πλήρους Θείας Λειτουργίας"), true);
        addServiceButton(card, services, "orthros", local("صلاة السحر", "Orthros", "Ὄρθρος"), false);
        addServiceButton(card, services, "vespers", local("صلاة الغروب", "Vespers", "Ἑσπερινός"), false);
        addServiceButton(card, services, "morning_prayer", local("صلوات الصباح", "Morning prayers", "Πρωινὲς προσευχές"), false);
        addServiceButton(card, services, "evening_prayer", local("صلوات المساء", "Evening prayers", "Ἑσπερινὲς προσευχές"), false);
        addServiceButton(card, services, "small_compline", local("صلاة النوم الصغرى", "Small Compline", "Μικρὸν Ἀπόδειπνον"), false);
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
