package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.List;

public final class BibleTestamentScreen extends BaseScreen {
    private final boolean newTestament;
    private final BibleCorpusRepository bible;

    public BibleTestamentScreen(ScreenHost host, String testament) {
        super(host);
        newTestament = "new".equals(testament);
        bible = new BibleCorpusRepository(host.activity());
    }

    @Override public View createView() {
        String lang = preferences.effectiveLanguage();
        UiKit.Page page = page(local(newTestament
                ? R.string.ui_bible_new_testament
                : R.string.ui_bible_old_testament), true);

        LinearLayout books = new LinearLayout(host.activity());
        books.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(books, new LinearLayout.LayoutParams(-1, -2));
        books.addView(centered(local(R.string.ui_bible_loading_books), 14, ui.colors().secondaryText(), false));

        new Thread(() -> {
            try {
                List<BibleCorpusRepository.BookInfo> list = bible.books(lang);
                books.post(() -> {
                    books.removeAllViews();
                    for (BibleCorpusRepository.BookInfo book : list) {
                        if (BibleBookNames.isNewTestament(book.code) != newTestament) continue;
                        LinearLayout card = ui.actionCard(
                                R.drawable.ic_action_readings,
                                BibleBookNames.name(book.code, lang),
                                localFormat(R.string.ui_bible_chapter_count, book.chapterCount));
                        card.setOnClickListener(v -> host.navigate("bible_book", book.code));
                        add(books, card, 2, 6);
                    }
                });
            } catch (Exception error) {
                books.post(() -> {
                    books.removeAllViews();
                    add(books, centered(local(R.string.ui_bible_full_corpus_unavailable), 14, ui.colors().secondaryText(), false), 10, 10);
                });
            }
        }, "BibleTestamentBooks").start();

        return page.scroll;
    }
}
