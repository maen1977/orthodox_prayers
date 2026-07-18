package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Context;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.data.SearchEngine;
import com.orthodoxprayers.privateapp.model.SearchResult;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class SearchScreen extends BaseScreen {
    private static final String TAG = "OrthodoxSearch";
    public SearchScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("البحث", "Search", "Ἀναζήτηση"), true);
        EditText input = new EditText(host.activity());
        input.setSingleLine(true);
        input.setText(preferences.lastSearchQuery());
        input.setHint(local("ابحث بآية أو مرجع أو صلاة، مثل: يوحنا 3:16", "Search by verse, reference, prayer, or liturgy", "Ἀναζήτηση στίχου, παραπομπῆς ἢ ἀκολουθίας"));
        input.setTextColor(ui.colors().primaryText());
        input.setHintTextColor(ui.colors().secondaryText());
        input.setTextSize(17 * preferences.fontScale());
        input.setPadding(ui.dp(12), ui.dp(8), ui.dp(12), ui.dp(8));
        input.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        ui.applyTextDirection(input, input.getHint().toString());
        input.setContentDescription(local("حقل البحث في الكتاب المقدس والصلوات والقداس", "Search Scripture, prayers, and liturgy", "Πεδίο ἀναζήτησης Γραφῆς καὶ ἀκολουθιῶν"));
        add(page.root, input, 14, 7);

        LinearLayout recentQueries = new LinearLayout(host.activity());
        recentQueries.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(recentQueries, new LinearLayout.LayoutParams(-1, -2));

        Button search = ui.button(local("بحث", "Search", "Ἀναζήτηση"), false);
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
                TextView message = centered(local("اكتب كلمة أو مرجعًا للبحث في النصوص الأصلية المعتمدة.",
                        "Type a word or reference to search approved native-source text.",
                        "Γράψτε λέξη ἢ παραπομπή γιὰ ἀναζήτηση στὸ ἐγκεκριμένο πρωτότυπο κείμενο."), 15, ui.colors().secondaryText(), false);
                add(results, message, 20, 20);
                return;
            }
            ArrayList<SearchResult> matches = SearchEngine.search(data, query);
            if (matches.isEmpty()) {
                TextView message = centered(local("لا توجد نتيجة مطابقة.", "No matching result.", "Δεν βρέθηκε αποτέλεσμα."), 16, ui.colors().secondaryText(), false);
                add(results, message, 20, 20);
                return;
            }
            TextView count = centered(local("عدد النتائج: ", "Results: ", "Αποτελέσματα: ") + matches.size(), 13, ui.colors().secondaryText(), true);
            add(results, count, 0, 8);
            for (SearchResult match : matches) add(results, resultCard(match), 2, 8);
        };
        List<String> history = preferences.searchHistory();
        if (!history.isEmpty()) {
            TextView recentTitle = ui.sectionTitle(local("عمليات البحث الأخيرة", "Recent searches", "Πρόσφατες ἀναζητήσεις"));
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
            Button clear = ui.smallButton(local("مسح سجل البحث", "Clear search history", "Καθαρισμὸς ἱστορικοῦ"), false);
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
        card.addView(ui.text(service.optString("icon", "☦") + "  " + title, 18, ui.colors().primaryText(), true));
        if (!result.matchedSection.isEmpty()) {
            TextView matched = ui.badge(local("المطابقة: ", "Matched in: ", "Βρέθηκε στὸ: ") + result.matchedSection, true);
            card.addView(matched, ui.margins(-1, -2, 0, 5, 0, 5));
        }
        TextView snippet = ui.text(result.snippet, 14, ui.colors().secondaryText(), false);
        snippet.setMaxLines(7);
        card.addView(snippet);
        Button open = ui.smallButton(local("فتح النتيجة", "Open result", "Ἄνοιγμα"), false);
        open.setOnClickListener(v -> host.navigate("reader", service.optString("id")));
        card.addView(open, ui.margins(-1, -2, 0, 7, 0, 0));
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
