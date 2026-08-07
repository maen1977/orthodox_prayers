package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

public final class BibleChapterScreen extends BaseScreen {
    private final String book;
    private final int chapter;
    private final BibleCorpusRepository bible;

    public BibleChapterScreen(ScreenHost host, String argument) {
        super(host);
        String[] parts = argument == null ? new String[0] : argument.split(":", 2);
        book = parts.length > 0 ? parts[0] : "";
        int parsed = 1;
        try { if (parts.length > 1) parsed = Integer.parseInt(parts[1]); } catch (Exception ignored) { }
        chapter = Math.max(1, parsed);
        bible = new BibleCorpusRepository(host.activity());
    }

    @Override public View createView() {
        String lang = preferences.effectiveLanguage();
        String title = BibleBookNames.name(book, lang) + " " + chapter;
        UiKit.Page page = page(title, true);
        LinearLayout holder = ui.card();
        add(page.root, holder, 12, 8);
        holder.addView(centered(local(R.string.ui_bible_loading_text), 14, ui.colors().secondaryText(), false));

        new Thread(() -> {
            try {
                BibleCorpusRepository.Chapter value = bible.chapter(lang, book, chapter);
                StringBuilder plain = new StringBuilder();
                for (BibleCorpusRepository.Verse verse : value.verses) {
                    if (plain.length() > 0) plain.append("\n");
                    plain.append(verse.verse).append(". ").append(verse.text);
                }
                String text = plain.toString();
                holder.post(() -> {
                    holder.removeAllViews();
                    holder.addView(ui.text(text.isEmpty() ? local(R.string.ui_bible_text_unavailable) : text,
                            17, ui.colors().primaryText(), false));
                    if (!text.isEmpty()) {
                        Button share = ui.smallButton(local(R.string.ui_bible_share_chapter), false);
                        share.setOnClickListener(v -> {
                            Intent intent = new Intent(Intent.ACTION_SEND);
                            intent.setType("text/plain");
                            intent.putExtra(Intent.EXTRA_TEXT, title + "\n\n" + text);
                            try { host.activity().startActivity(Intent.createChooser(intent, title)); } catch (Exception ignored) { }
                        });
                        holder.addView(share, ui.margins(-1, -2, 0, 10, 0, 0));
                    }
                });
            } catch (Exception error) {
                holder.post(() -> {
                    holder.removeAllViews();
                    holder.addView(centered(local(R.string.ui_bible_cannot_open_text), 14, ui.colors().secondaryText(), false));
                });
            }
        }, "BibleChapter").start();
        return page.scroll;
    }
}
