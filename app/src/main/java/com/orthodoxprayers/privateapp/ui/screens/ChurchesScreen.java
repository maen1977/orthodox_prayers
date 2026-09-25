package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.net.Uri;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.data.SearchEngine;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;

public final class ChurchesScreen extends BaseScreen {
    private static final String ROUTE_HOME = "home";
    private static final String ROUTE_LIVE = "live";
    private static final String ROUTE_SOURCES = "sources";
    private static final String ROUTE_DIRECTORY = "directory";
    private static final String ROUTE_SOURCE = "source";
    private static final String ROUTE_GROUP = "group";
    private static final String ROUTE_CITY = "city";

    private final String route;

    public ChurchesScreen(ScreenHost host) {
        this(host, ROUTE_HOME);
    }

    public ChurchesScreen(ScreenHost host, String argument) {
        super(host);
        this.route = argument == null || argument.trim().isEmpty() ? ROUTE_HOME : argument.trim();
    }

    @Override
    public View createView() {
        String[] parts = route.split("\\|", -1);
        if (ROUTE_LIVE.equals(route)) return createLiveResourcesView();
        if (ROUTE_SOURCES.equals(route)) return createDirectorySourcesView();
        if (ROUTE_DIRECTORY.equals(route)) return createDirectoryGroupsView();
        if (parts.length >= 2 && ROUTE_SOURCE.equals(parts[0])) return createSourceChurchesView(parts[1]);
        if (parts.length >= 2 && ROUTE_GROUP.equals(parts[0])) return createGroupCitiesView(parts[1]);
        if (parts.length >= 3 && ROUTE_CITY.equals(parts[0])) return createCityChurchesView(parts[1], parts[2]);
        return createHomeView();
    }

    private View createHomeView() {
        UiKit.Page page = page(local(R.string.ui_churches_and_live_services_7171f5ce), true);
        int count = data.registeredChurches().length();
        add(page.root, ui.infoBadge(localFormat(R.string.ui_church_directory_count_format, count)), 10, 9);
        add(page.root, ui.sectionTitle(local(R.string.ui_church_cards_choose_section_2d4b2f1a)), 0, 0);

        addActionCard(page.root,
                ui.actionCard(R.drawable.ic_nav_liturgy,
                        local(R.string.ui_official_live_resources_86f88e7a),
                        local(R.string.ui_church_live_card_subtitle_4d9b3d21)),
                () -> host.navigate("churches", ROUTE_LIVE));
        addActionCard(page.root,
                ui.actionCard(R.drawable.ic_nav_prayers,
                        local(R.string.ui_official_directory_sources_r62),
                        local(R.string.ui_church_sources_card_subtitle_6b7a2c13)),
                () -> host.navigate("churches", ROUTE_SOURCES));
        addActionCard(page.root,
                ui.actionCard(R.drawable.ic_nav_home,
                        local(R.string.ui_church_directory_36e0707d),
                        local(R.string.ui_church_directory_card_subtitle_91a4f0d2)),
                () -> host.navigate("churches", ROUTE_DIRECTORY));
        return page.scroll;
    }

    private View createLiveResourcesView() {
        UiKit.Page page = page(local(R.string.ui_official_live_resources_86f88e7a), true);
        JSONArray resources = data.officialLiveResources();
        if (resources.length() == 0) {
            addEmpty(page.root);
            return page.scroll;
        }
        for (int i = 0; i < resources.length(); i++) {
            JSONObject resource = resources.optJSONObject(i);
            if (resource == null) continue;
            addExternalResourceCard(page.root, resource, R.drawable.ic_nav_liturgy);
        }
        return page.scroll;
    }

    private View createDirectorySourcesView() {
        UiKit.Page page = page(local(R.string.ui_official_directory_sources_r62), true);
        add(page.root, ui.infoBadge(local(R.string.ui_church_directory_official_source_note_r66)), 10, 9);
        add(page.root, ui.infoBadge(local(R.string.ui_church_directory_sync_enabled_r66)), 10, 9);
        add(page.root, ui.infoBadge(directorySyncStatus()), 10, 9);
        JSONArray resources = data.officialChurchDirectoryResources();
        if (resources.length() == 0) {
            addEmpty(page.root);
            return page.scroll;
        }
        for (int i = 0; i < resources.length(); i++) {
            JSONObject resource = resources.optJSONObject(i);
            if (resource == null) continue;
            String sourceId = resource.optString("id", "").trim();
            String title = data.metadataLocalized(resource.optJSONObject("title"),
                    local(R.string.ui_official_church_link_2d1a8bdb));
            String subtitle = localFormat(R.string.ui_church_directory_source_count_format_r66,
                    countChurchesFromSource(sourceId));
            addActionCard(page.root,
                    ui.actionCard(R.drawable.ic_nav_prayers, title, subtitle),
                    () -> host.navigate("churches", ROUTE_SOURCE + "|" + sourceId));
        }
        return page.scroll;
    }

    private View createSourceChurchesView(String sourceId) {
        JSONObject resource = findSource(sourceId);
        String title = resource == null
                ? local(R.string.ui_official_directory_sources_r62)
                : data.metadataLocalized(resource.optJSONObject("title"),
                        local(R.string.ui_official_directory_sources_r62));
        UiKit.Page page = page(title, true);
        add(page.root, ui.infoBadge(local(R.string.ui_church_directory_internal_subtitle_r66)), 10, 9);
        JSONArray churches = data.registeredChurches();
        int shown = 0;
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null || !belongsToSource(church, sourceId)) continue;
            String name = data.metadataLocalized(church.optJSONObject("name"),
                    local(R.string.ui_official_parish_name_unavailable_in_english_eea6633c));
            String city = data.metadataLocalized(church.optJSONObject("city"), "");
            add(page.root, churchCard(church, name, city), 1, 7);
            shown++;
        }
        if (shown == 0) addEmpty(page.root);
        return page.scroll;
    }

    private View createDirectoryGroupsView() {
        UiKit.Page page = page(local(R.string.ui_church_directory_36e0707d), true);
        Map<String, JSONObject> groups = collectGroups();
        if (groups.isEmpty()) {
            addEmpty(page.root);
            return page.scroll;
        }
        add(page.root, ui.sectionTitle(local(R.string.ui_church_cards_choose_region_7f9e3a41)), 0, 0);
        add(page.root, ui.infoBadge(directorySyncStatus()), 10, 9);
        for (Map.Entry<String, JSONObject> entry : groups.entrySet()) {
            String groupId = entry.getKey();
            JSONObject group = entry.getValue();
            String title = data.metadataLocalized(group.optJSONObject("region"),
                    data.metadataLocalized(group.optJSONObject("country"),
                            local(R.string.ui_church_region_unavailable_0a42b8c1)));
            String subtitle = localFormat(R.string.ui_churches_count_short_format_5f73c9b2,
                    countChurchesInGroup(groupId));
            addActionCard(page.root,
                    ui.actionCard(R.drawable.ic_nav_home, title, subtitle),
                    () -> host.navigate("churches", ROUTE_GROUP + "|" + groupId));
        }
        return page.scroll;
    }

    private View createGroupCitiesView(String groupId) {
        JSONObject group = findGroup(groupId);
        String groupTitle = group == null
                ? local(R.string.ui_church_directory_36e0707d)
                : data.metadataLocalized(group.optJSONObject("region"),
                        data.metadataLocalized(group.optJSONObject("country"),
                                local(R.string.ui_church_directory_36e0707d)));
        UiKit.Page page = page(groupTitle, true);
        Map<String, JSONObject> cities = collectCities(groupId);
        if (cities.isEmpty()) {
            addEmpty(page.root);
            return page.scroll;
        }
        add(page.root, ui.sectionTitle(local(R.string.ui_church_cards_choose_city_3c1d8e74)), 0, 0);
        for (Map.Entry<String, JSONObject> entry : cities.entrySet()) {
            String cityKey = entry.getKey();
            JSONObject city = entry.getValue();
            String title = data.metadataLocalized(city, local(R.string.ui_church_directory_36e0707d));
            String subtitle = localFormat(R.string.ui_churches_count_short_format_5f73c9b2,
                    countChurchesInCity(groupId, cityKey));
            addActionCard(page.root,
                    ui.actionCard(R.drawable.ic_nav_prayers, title, subtitle),
                    () -> host.navigate("churches", ROUTE_CITY + "|" + groupId + "|" + cityKey));
        }
        return page.scroll;
    }

    private View createCityChurchesView(String groupId, String cityKey) {
        JSONObject city = findCity(groupId, cityKey);
        String title = city == null
                ? local(R.string.ui_church_directory_36e0707d)
                : data.metadataLocalized(city, local(R.string.ui_church_directory_36e0707d));
        UiKit.Page page = page(title, true);
        EditText query = new EditText(host.activity());
        query.setSingleLine(true);
        query.setHint(local(R.string.ui_search_by_church_or_city_556a72f2));
        query.setTextColor(ui.colors().primaryText());
        query.setHintTextColor(ui.colors().secondaryText());
        query.setTextSize(16 * preferences.fontScale());
        query.setPadding(ui.dp(12), ui.dp(8), ui.dp(12), ui.dp(8));
        query.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        add(page.root, query, 0, 8);

        LinearLayout results = new LinearLayout(host.activity());
        results.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(results, new LinearLayout.LayoutParams(-1, -2));
        Runnable render = () -> renderChurches(results, query.getText().toString(), groupId, cityKey);
        query.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { render.run(); }
            @Override public void afterTextChanged(Editable s) {}
        });
        render.run();
        return page.scroll;
    }

    private Map<String, JSONObject> collectGroups() {
        Map<String, JSONObject> groups = new LinkedHashMap<>();
        JSONArray churches = data.registeredChurches();
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null) continue;
            String groupId = church.optString("region_id", church.optString("country_group", "other")).trim();
            if (!groups.containsKey(groupId)) groups.put(groupId, church);
        }
        return groups;
    }

    private JSONObject findSource(String sourceId) {
        JSONArray resources = data.officialChurchDirectoryResources();
        for (int i = 0; i < resources.length(); i++) {
            JSONObject resource = resources.optJSONObject(i);
            if (resource != null && sourceId.equals(resource.optString("id", ""))) return resource;
        }
        return null;
    }

    private int countChurchesFromSource(String sourceId) {
        int count = 0;
        JSONArray churches = data.registeredChurches();
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church != null && belongsToSource(church, sourceId)) count++;
        }
        return count;
    }

    private boolean belongsToSource(JSONObject church, String sourceId) {
        if (church == null || sourceId == null || sourceId.trim().isEmpty()) return false;
        if (sourceId.equals(church.optString("source_id", "").trim())) return true;
        org.json.JSONArray sourceIds = church.optJSONArray("directory_source_ids");
        if (sourceIds == null) return false;
        for (int i = 0; i < sourceIds.length(); i++) {
            if (sourceId.equals(sourceIds.optString(i, "").trim())) return true;
        }
        return false;
    }

    private String directorySyncStatus() {
        return preferences.churchDirectoryLastSyncSucceeded()
                ? local(R.string.ui_church_directory_sync_verified_r66)
                : local(R.string.ui_church_directory_sync_waiting_r66);
    }

    private Map<String, JSONObject> collectCities(String groupId) {
        Map<String, JSONObject> cities = new LinkedHashMap<>();
        JSONArray churches = data.registeredChurches();
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null || !groupId.equals(church.optString("region_id", church.optString("country_group", "other")))) continue;
            JSONObject city = church.optJSONObject("city");
            String key = city == null ? "" : city.optString("en", city.optString("ar", "")).trim();
            if (!key.isEmpty() && !cities.containsKey(key)) cities.put(key, city);
        }
        return cities;
    }

    private JSONObject findGroup(String groupId) {
        return collectGroups().get(groupId);
    }

    private JSONObject findCity(String groupId, String cityKey) {
        return collectCities(groupId).get(cityKey);
    }

    private int countChurchesInGroup(String groupId) {
        int count = 0;
        JSONArray churches = data.registeredChurches();
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church != null && groupId.equals(church.optString("region_id", church.optString("country_group", "other")))) count++;
        }
        return count;
    }

    private int countChurchesInCity(String groupId, String cityKey) {
        int count = 0;
        JSONArray churches = data.registeredChurches();
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null || !groupId.equals(church.optString("region_id", church.optString("country_group", "other")))) continue;
            JSONObject city = church.optJSONObject("city");
            String key = city == null ? "" : city.optString("en", city.optString("ar", "")).trim();
            if (cityKey.equals(key)) count++;
        }
        return count;
    }

    private void renderChurches(LinearLayout root, String rawQuery, String groupId, String cityKey) {
        root.removeAllViews();
        String query = SearchEngine.normalize(rawQuery);
        JSONArray churches = data.registeredChurches();
        int shown = 0;
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null || !groupId.equals(church.optString("region_id", church.optString("country_group", "other")))) continue;
            JSONObject city = church.optJSONObject("city");
            String key = city == null ? "" : city.optString("en", city.optString("ar", "")).trim();
            if (!cityKey.equals(key)) continue;

            String name = data.metadataLocalized(church.optJSONObject("name"),
                    local(R.string.ui_official_parish_name_unavailable_in_english_eea6633c));
            String cityName = data.metadataLocalized(city, "");
            String country = data.metadataLocalized(church.optJSONObject("country"), "");
            String searchable = SearchEngine.normalize(name + " " + cityName + " " + country);
            if (!query.isEmpty() && !searchable.contains(query)) continue;
            add(root, churchCard(church, name, cityName), 1, 7);
            shown++;
        }
        if (shown == 0) addEmpty(root);
    }

    private void addExternalResourceCard(LinearLayout root, JSONObject resource, int icon) {
        String title = data.metadataLocalized(resource.optJSONObject("title"),
                local(R.string.ui_official_church_link_2d1a8bdb));
        LinearLayout card = ui.actionCard(icon, title,
                local(R.string.ui_open_official_link_subtitle_8d2f6c10));
        String url = resource.optString("url", "");
        card.setOnClickListener(v -> openUrl(url));
        add(root, card, 0, 8);
    }

    private void addActionCard(LinearLayout root, LinearLayout card, Runnable action) {
        card.setOnClickListener(v -> action.run());
        add(root, card, 0, 8);
    }

    private void addEmpty(LinearLayout root) {
        TextView empty = centered(local(R.string.ui_no_matching_church_in_the_current_directory_d42641ca),
                14, ui.colors().secondaryText(), false);
        add(root, empty, 16, 16);
    }

    private LinearLayout churchCard(JSONObject church, String name, String city) {
        LinearLayout card = ui.card();
        card.addView(ui.text(name, 17, ui.colors().primaryText(), true));
        if (!city.isEmpty()) card.addView(ui.text(city, 13, ui.colors().secondaryText(), false),
                ui.margins(-1, -2, 0, 4, 0, 0));
        card.addView(ui.text(local(R.string.ui_service_times_may_change_by_season_and_feast_the_7a56811a),
                12, ui.colors().secondaryText(), false));
        String url = church.optString("url", "");
        android.widget.Button open = ui.smallButton(local(R.string.ui_open_parish_page_f8727b57), false);
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
            Toast.makeText(host.activity(), local(R.string.ui_could_not_open_the_official_link_3126ea33),
                    Toast.LENGTH_SHORT).show();
        }
    }
}
