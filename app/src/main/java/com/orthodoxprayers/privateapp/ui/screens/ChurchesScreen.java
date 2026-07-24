package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.net.Uri;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.data.SearchEngine;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class ChurchesScreen extends BaseScreen {
    public ChurchesScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("الكنائس والبث", "Churches and live services", "Ναοὶ καὶ ζωντανὲς μεταδόσεις"), true);
        JSONObject directory = data.churchDirectory();
        int count = data.registeredChurches().length();
        add(page.root, ui.infoBadge(local(
                "دليل رسمي من مطرانية الأردن. عدد الروابط الحالية: " + count + ". افتح صفحة الكنيسة للتأكد من مواعيد القداس الحالية.",
                "Official Orthodox Jordan directory. Current links: " + count + ". Open the parish page to confirm current service times.",
                "Ἐπίσημος κατάλογος Ἰορδανίας. Σύνδεσμοι: " + count + ". Ἐλέγξτε τὸ τρέχον πρόγραμμα στὴν ἐπίσημη σελίδα."
        )), 10, 9);

        JSONArray resources = mergeResources(data.officialLiveResources(), data.officialServiceLinks());
        if (resources.length() > 0) {
            page.root.addView(ui.sectionTitle(local("روابط كنسية مباشرة", "Official live resources", "Ἐπίσημοι ζωντανοὶ σύνδεσμοι")));
            for (int i = 0; i < resources.length(); i++) {
                JSONObject resource = resources.optJSONObject(i);
                if (resource == null) continue;
                String title = data.metadataLocalized(
                        resource.optJSONObject("title"),
                        local("رابط كنسي رسمي", "Official church link", "Ἐπίσημος ἐκκλησιαστικὸς σύνδεσμος")
                );
                Button open = ui.button("▶  " + title, false);
                String url = resource.optString("url", "");
                open.setOnClickListener(v -> openUrl(url));
                add(page.root, open, 0, 6);
            }
        }

        page.root.addView(ui.sectionTitle(local("دليل الكنائس", "Church directory", "Κατάλογος ναῶν")));
        EditText query = new EditText(host.activity());
        query.setSingleLine(true);
        query.setHint(local("ابحث باسم الكنيسة أو المدينة", "Search by church or city", "Ἀναζήτηση ναοῦ ἢ πόλης"));
        query.setTextColor(ui.colors().primaryText());
        query.setHintTextColor(ui.colors().secondaryText());
        query.setTextSize(16 * preferences.fontScale());
        query.setPadding(ui.dp(12), ui.dp(8), ui.dp(12), ui.dp(8));
        query.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        add(page.root, query, 0, 8);

        LinearLayout results = new LinearLayout(host.activity());
        results.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(results, new LinearLayout.LayoutParams(-1, -2));

        Runnable render = () -> renderChurches(results, query.getText().toString());
        query.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { render.run(); }
            @Override public void afterTextChanged(Editable s) {}
        });
        render.run();
        return page.scroll;
    }

    private JSONArray mergeResources(JSONArray first, JSONArray second) {
        JSONArray result = new JSONArray();
        for (int i = 0; i < first.length(); i++) result.put(first.opt(i));
        for (int i = 0; i < second.length(); i++) result.put(second.opt(i));
        return result;
    }

    private void renderChurches(LinearLayout root, String rawQuery) {
        root.removeAllViews();
        String query = SearchEngine.normalize(rawQuery);
        JSONArray churches = data.registeredChurches();
        int shown = 0;
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null) continue;
            String name = data.metadataLocalized(
                    church.optJSONObject("name"),
                    local(
                            "اسم الرعية الرسمي غير متوفر بالعربية",
                            "Official parish name unavailable in English",
                            "Ἡ ἐπίσημη ὀνομασία τῆς ἐνορίας δὲν διατίθεται στὰ ἑλληνικά"
                    )
            );
            String city = data.metadataLocalized(church.optJSONObject("city"), "");
            String searchable = SearchEngine.normalize(name + " " + city);
            if (!query.isEmpty() && !searchable.contains(query)) continue;
            add(root, churchCard(church, name, city), 1, 7);
            shown++;
        }
        if (shown == 0) {
            TextView empty = centered(local("لا توجد كنيسة مطابقة في الدليل الحالي.", "No matching church in the current directory.", "Δὲν βρέθηκε ναός."),
                    14, ui.colors().secondaryText(), false);
            add(root, empty, 16, 16);
        }
    }

    private LinearLayout churchCard(JSONObject church, String name, String city) {
        LinearLayout card = ui.card();
        card.addView(ui.text("⛪  " + name, 17, ui.colors().primaryText(), true));
        if (!city.isEmpty()) card.addView(ui.text(city, 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
        card.addView(ui.text(local(
                "المواعيد تتغير حسب الموسم والعيد؛ المصدر الرسمي هو المرجع الحالي.",
                "Service times may change by season and feast; the official page is the current authority.",
                "Τὸ πρόγραμμα μεταβάλλεται· ἡ ἐπίσημη σελίδα εἶναι ἡ τρέχουσα πηγή."
        ), 12, ui.colors().secondaryText(), false));
        String url = church.optString("url", "");
        Button open = ui.smallButton(local("فتح صفحة الكنيسة", "Open parish page", "Ἄνοιγμα σελίδας ναοῦ"), false);
        open.setOnClickListener(v -> openUrl(url));
        card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
        return card;
    }

    private void openUrl(String url) {
        try {
            if (url == null || !url.startsWith("https://")) throw new IllegalArgumentException("invalid URL");
            host.activity().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception error) {
            Toast.makeText(host.activity(), local("تعذر فتح الرابط الرسمي.", "Could not open the official link.", "Δὲν ἄνοιξε ὁ ἐπίσημος σύνδεσμος."), Toast.LENGTH_SHORT).show();
        }
    }
}
