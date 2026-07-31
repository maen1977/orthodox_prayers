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
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_churches_and_live_services_7171f5ce), true);
        JSONObject directory = data.churchDirectory();
        int count = data.registeredChurches().length();
        add(page.root, ui.infoBadge(localFormat(
                com.orthodoxprayers.privateapp.R.string.ui_church_directory_count_format,
                count
        )), 10, 9);

        JSONArray resources = mergeResources(data.officialLiveResources(), data.officialServiceLinks());
        if (resources.length() > 0) {
            page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_official_live_resources_86f88e7a)));
            for (int i = 0; i < resources.length(); i++) {
                JSONObject resource = resources.optJSONObject(i);
                if (resource == null) continue;
                String title = data.metadataLocalized(
                        resource.optJSONObject("title"),
                        local(com.orthodoxprayers.privateapp.R.string.ui_official_church_link_2d1a8bdb)
                );
                Button open = ui.button("▶  " + title, false);
                String url = resource.optString("url", "");
                open.setOnClickListener(v -> openUrl(url));
                add(page.root, open, 0, 6);
            }
        }

        page.root.addView(ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_church_directory_36e0707d)));
        EditText query = new EditText(host.activity());
        query.setSingleLine(true);
        query.setHint(local(com.orthodoxprayers.privateapp.R.string.ui_search_by_church_or_city_556a72f2));
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
                    local(com.orthodoxprayers.privateapp.R.string.ui_official_parish_name_unavailable_in_english_eea6633c)
            );
            String city = data.metadataLocalized(church.optJSONObject("city"), "");
            String searchable = SearchEngine.normalize(name + " " + city);
            if (!query.isEmpty() && !searchable.contains(query)) continue;
            add(root, churchCard(church, name, city), 1, 7);
            shown++;
        }
        if (shown == 0) {
            TextView empty = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_matching_church_in_the_current_directory_d42641ca),
                    14, ui.colors().secondaryText(), false);
            add(root, empty, 16, 16);
        }
    }

    private LinearLayout churchCard(JSONObject church, String name, String city) {
        LinearLayout card = ui.card();
        card.addView(ui.text(name, 17, ui.colors().primaryText(), true));
        if (!city.isEmpty()) card.addView(ui.text(city, 13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
        card.addView(ui.text(local(com.orthodoxprayers.privateapp.R.string.ui_service_times_may_change_by_season_and_feast_the_7a56811a), 12, ui.colors().secondaryText(), false));
        String url = church.optString("url", "");
        Button open = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_open_parish_page_f8727b57), false);
        open.setOnClickListener(v -> openUrl(url));
        card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
        return card;
    }

    private void openUrl(String url) {
        try {
            if (url == null || !url.startsWith("https://")) throw new IllegalArgumentException("invalid URL");
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addCategory(Intent.CATEGORY_BROWSABLE);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_DOCUMENT);
            host.activity().startActivity(intent);
        } catch (Exception error) {
            Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_could_not_open_the_official_link_3126ea33), Toast.LENGTH_SHORT).show();
        }
    }
}
