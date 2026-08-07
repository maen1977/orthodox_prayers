package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.List;

public final class BibleScreen extends BaseScreen {
    private final BibleCorpusRepository bible;

    public BibleScreen(ScreenHost host) {
        super(host);
        bible = new BibleCorpusRepository(host.activity());
    }

    @Override public View createView() {
        String lang = preferences.effectiveLanguage();
        UiKit.Page page = page(local(R.string.ui_bible_title), true);

        LinearLayout intro = ui.card();
        intro.addView(ui.text(local(R.string.ui_bible_intro), 14, ui.colors().secondaryText(), false));
        intro.addView(ui.badge(local(R.string.ui_bible_source_label), true), ui.margins(-1, -2, 0, 7, 0, 0));
        add(page.root, intro, 12, 10);

        EditText query = new EditText(host.activity());
        query.setSingleLine(true);
        query.setHint(local(R.string.ui_bible_search_hint));
        query.setTextColor(ui.colors().primaryText());
        query.setHintTextColor(ui.colors().secondaryText());
        query.setTextSize(16 * preferences.fontScale());
        query.setPadding(ui.dp(12), ui.dp(8), ui.dp(12), ui.dp(8));
        query.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        add(page.root, query, 4, 6);

        Button search = ui.button(local(R.string.ui_bible_search), false);
        add(page.root, search, 0, 8);

        LinearLayout results = new LinearLayout(host.activity());
        results.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(results, new LinearLayout.LayoutParams(-1, -2));

        Runnable doSearch = () -> {
            String value = query.getText().toString().trim();
            if (value.isEmpty()) return;
            results.removeAllViews();
            results.addView(centered(local(R.string.ui_bible_searching), 14, ui.colors().secondaryText(), false));
            new Thread(() -> {
                try {
                    List<BibleCorpusRepository.SearchHit> hits = bible.search(lang, value, 80);
                    results.post(() -> {
                        results.removeAllViews();
                        if (hits.isEmpty()) {
                            add(results, centered(local(R.string.ui_bible_no_results), 14, ui.colors().secondaryText(), false), 8, 8);
                            return;
                        }
                        for (BibleCorpusRepository.SearchHit hit : hits) {
                            LinearLayout card = ui.card();
                            card.addView(ui.text(BibleBookNames.name(hit.book, lang) + " " + hit.chapter + ":" + hit.verse,
                                    16, ui.colors().accentText(), true));
                            card.addView(ui.text(hit.text, 14, ui.colors().primaryText(), false), ui.margins(-1, -2, 0, 4, 0, 0));
                            card.setOnClickListener(v -> host.navigate("bible_chapter", hit.book + ":" + hit.chapter));
                            add(results, card, 2, 6);
                        }
                    });
                } catch (Exception error) {
                    results.post(() -> {
                        results.removeAllViews();
                        add(results, centered(local(R.string.ui_bible_full_corpus_unavailable), 14, ui.colors().secondaryText(), false), 8, 8);
                    });
                }
            }, "BibleSearch").start();
        };
        search.setOnClickListener(v -> doSearch.run());
        query.setOnEditorActionListener((v, a, e) -> { doSearch.run(); return true; });

        LinearLayout oldTestament = ui.actionCard(
                R.drawable.ic_action_readings,
                local(R.string.ui_bible_old_testament),
                local(R.string.ui_bible_old_testament_summary));
        oldTestament.setOnClickListener(v -> host.navigate("bible_testament", "old"));
        add(page.root, oldTestament, 10, 6);

        LinearLayout newTestament = ui.actionCard(
                R.drawable.ic_action_readings,
                local(R.string.ui_bible_new_testament),
                local(R.string.ui_bible_new_testament_summary));
        newTestament.setOnClickListener(v -> host.navigate("bible_testament", "new"));
        add(page.root, newTestament, 2, 10);

        return page.scroll;
    }
}
