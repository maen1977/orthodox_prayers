package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.List;

public final class BibleBookScreen extends BaseScreen {
    private final String book;
    private final BibleCorpusRepository bible;

    public BibleBookScreen(ScreenHost host, String book) {
        super(host);
        this.book = book == null ? "" : book;
        bible = new BibleCorpusRepository(host.activity());
    }

    @Override public View createView() {
        String lang = preferences.effectiveLanguage();
        UiKit.Page page = page(BibleBookNames.name(book, lang), true);
        LinearLayout holder = new LinearLayout(host.activity());
        holder.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(holder, new LinearLayout.LayoutParams(-1, -2));
        holder.addView(centered(local(R.string.ui_bible_loading_chapters), 14, ui.colors().secondaryText(), false));

        new Thread(() -> {
            try {
                List<BibleCorpusRepository.BookInfo> books = bible.books(lang);
                int chapters = 0;
                for (BibleCorpusRepository.BookInfo value : books) {
                    if (book.equals(value.code)) {
                        chapters = value.chapterCount;
                        break;
                    }
                }
                final int count = chapters;
                holder.post(() -> {
                    holder.removeAllViews();
                    for (int i = 1; i <= count; i++) {
                        final int chapter = i;
                        LinearLayout card = ui.actionCard(
                                R.drawable.ic_action_readings,
                                localFormat(R.string.ui_bible_chapter_title, chapter),
                                BibleBookNames.name(book, lang));
                        card.setOnClickListener(v -> host.navigate("bible_chapter", book + ":" + chapter));
                        add(holder, card, 2, 6);
                    }
                });
            } catch (Exception error) {
                holder.post(() -> {
                    holder.removeAllViews();
                    holder.addView(centered(local(R.string.ui_bible_cannot_open_bundled_bible), 14, ui.colors().secondaryText(), false));
                });
            }
        }, "BibleBook").start();
        return page.scroll;
    }
}
