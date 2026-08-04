package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.data.SearchEngine;
import com.orthodoxprayers.privateapp.model.SearchResult;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class SearchScreen extends BaseScreen {
    private static final String TAG = "OrthodoxSearch";
    public SearchScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_search_13f179d6), true);
        EditText input = new EditText(host.activity());
        input.setSingleLine(true);
        input.setText(preferences.lastSearchQuery());
        input.setHint(local(com.orthodoxprayers.privateapp.R.string.ui_search_by_verse_reference_prayer_or_liturgy_74401ea3));
        input.setTextColor(ui.colors().primaryText());
        input.setHintTextColor(ui.colors().secondaryText());
        input.setTextSize(17 * preferences.fontScale());
        input.setPadding(ui.dp(12), ui.dp(8), ui.dp(12), ui.dp(8));
        input.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        ui.applyTextDirection(input, input.getHint().toString());
        input.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_search_scripture_prayers_and_liturgy_33e12057));
        add(page.root, input, 14, 7);

        LinearLayout recentQueries = new LinearLayout(host.activity());
        recentQueries.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(recentQueries, new LinearLayout.LayoutParams(-1, -2));

        Button search = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_search_f55b3d60), false);
        add(page.root, search, 0, 10);
        LinearLayout results = new LinearLayout(host.activity());
        results.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(results, new LinearLayout.LayoutParams(-1, -2));

        Runnable execute = () -> {
            String query = input.getText().toString().trim();
            preferences.setLastSearchQuery(query);
            preferences.recordSearchQuery(query);
            hideKeyboard(input);
            results.removeAllViews();
            if (query.isEmpty()) {
                TextView message = centered(local(com.orthodoxprayers.privateapp.R.string.ui_type_a_word_or_reference_to_search_approved_nati_703cdad7), 15, ui.colors().secondaryText(), false);
                add(results, message, 20, 20);
                return;
            }
            ArrayList<SearchResult> matches = SearchEngine.search(data, query);
            if (matches.isEmpty()) {
                TextView message = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_matching_result_65289b38), 16, ui.colors().secondaryText(), false);
                add(results, message, 20, 20);
                return;
            }
            TextView count = centered(local(com.orthodoxprayers.privateapp.R.string.ui_results_89a9233d) + matches.size(), 13, ui.colors().secondaryText(), true);
            add(results, count, 0, 8);
            for (SearchResult match : matches) add(results, resultCard(match), 2, 8);
        };
        List<String> history = preferences.searchHistory();
        if (!history.isEmpty()) {
            TextView recentTitle = ui.sectionTitle(local(com.orthodoxprayers.privateapp.R.string.ui_recent_searches_45974f02));
            recentQueries.addView(recentTitle);
            LinearLayout row = ui.row();
            for (int i = 0; i < Math.min(4, history.size()); i++) {
                String previous = history.get(i);
                Button item = ui.smallButton(previous, false);
                item.setMaxLines(1);
                item.setOnClickListener(v -> {
                    input.setText(previous);
                    input.setSelection(previous.length());
                    execute.run();
                });
                row.addView(item, ui.weight(44));
            }
            recentQueries.addView(row);
            Button clear = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_clear_search_history_abb8a916), false);
            clear.setOnClickListener(v -> {
                preferences.clearSearchHistory();
                recentQueries.removeAllViews();
            });
            recentQueries.addView(clear, ui.margins(-1, -2, 0, 4, 0, 7));
        }

        search.setOnClickListener(v -> execute.run());
        input.setOnEditorActionListener((v, actionId, event) -> { execute.run(); return true; });
        execute.run();
        return page.scroll;
    }

    private LinearLayout resultCard(SearchResult result) {
        JSONObject service = result.service;
        LinearLayout card = ui.card();
        String title = localized(service.optJSONObject("title"), "");
        card.addView(ui.text(title, 18, ui.colors().primaryText(), true));
        if (!result.matchedSection.isEmpty()) {
            TextView matched = ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_matched_in_d4d746e2) + result.matchedSection, true);
            card.addView(matched, ui.margins(-1, -2, 0, 5, 0, 5));
        }
        TextView snippet = ui.text(result.snippet, 14, ui.colors().secondaryText(), false);
        snippet.setMaxLines(7);
        card.addView(snippet);
        String externalUrl = service.optString("external_url", "").trim();
        LinearLayout actions = ui.row();
        Button open = ui.smallButton(externalUrl.isEmpty()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_open_result_269ccae8)
                : local(com.orthodoxprayers.privateapp.R.string.ui_open_official_link_aeec6baa), false);
        open.setOnClickListener(v -> {
            if (externalUrl.isEmpty()) {
                host.navigate("reader", service.optString("id"));
                return;
            }
            try {
                host.activity().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(externalUrl)));
            } catch (Exception error) {
                Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_could_not_open_the_official_link_3126ea33), Toast.LENGTH_SHORT).show();
            }
        });
        actions.addView(open, ui.weight(50));
        String serviceId = service.optString("id", "").trim();
        if (externalUrl.isEmpty() && !serviceId.isEmpty()) {
            Button favorite = ui.smallButton(
                    preferences.isFavorite(serviceId)
                            ? local(com.orthodoxprayers.privateapp.R.string.ui_saved_cd7c1a66)
                            : local(com.orthodoxprayers.privateapp.R.string.ui_favorite_1d799489),
                    preferences.isFavorite(serviceId)
            );
            favorite.setOnClickListener(v -> {
                preferences.toggleFavorite(serviceId);
                boolean active = preferences.isFavorite(serviceId);
                String label = active
                        ? local(com.orthodoxprayers.privateapp.R.string.ui_saved_cd7c1a66)
                        : local(com.orthodoxprayers.privateapp.R.string.ui_favorite_1d799489);
                favorite.setText(label);
                favorite.setTextColor(active ? android.graphics.Color.WHITE : ui.colors().primaryText());
                favorite.setBackground(ui.round(
                        active ? ThemePalette.NAVY : ui.colors().card(),
                        ThemePalette.GOLD,
                        14
                ));
                favorite.setContentDescription(label);
            });
            actions.addView(favorite, ui.weight(50));
        }
        card.addView(actions, ui.margins(-1, -2, 0, 7, 0, 0));
        card.setContentDescription(title + ". " + result.snippet);
        return card;
    }

    private void hideKeyboard(View view) {
        try {
            InputMethodManager manager = (InputMethodManager) host.activity().getSystemService(Context.INPUT_METHOD_SERVICE);
            if (manager != null) manager.hideSoftInputFromWindow(view.getWindowToken(), 0);
        } catch (Exception error) {
            Log.w(TAG, "Could not hide keyboard", error);
        }
    }
}
