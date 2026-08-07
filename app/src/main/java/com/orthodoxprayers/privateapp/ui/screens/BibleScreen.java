package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import java.util.List;

public final class BibleScreen extends BaseScreen {
    private final BibleCorpusRepository bible;
    public BibleScreen(ScreenHost host) { super(host); bible = new BibleCorpusRepository(host.activity()); }

    @Override public View createView() {
        String lang = preferences.effectiveLanguage();
        UiKit.Page page = page(t(lang, "الكتاب المقدس", "Holy Bible", "Ἁγία Γραφή"), true);
        LinearLayout intro = ui.card();
        intro.addView(ui.text(t(lang,
                "النص محفوظ داخل التطبيق ويعمل دون إنترنت. قراءة اليوم تستخدم نفس النص الكامل.",
                "The text is stored inside the app and works offline. Daily readings use this same full corpus.",
                "Τὸ κείμενο εἶναι ἀποθηκευμένο μέσα στὴν ἐφαρμογὴ καὶ λειτουργεῖ χωρὶς διαδίκτυο. Τὰ καθημερινὰ ἀναγνώσματα χρησιμοποιοῦν τὸ ἴδιο πλήρες σώμα κειμένου."),
                14, ui.colors().secondaryText(), false));
        intro.addView(ui.badge(sourceLabel(lang), true), ui.margins(-1,-2,0,7,0,0));
        add(page.root, intro, 12, 10);

        EditText query = new EditText(host.activity());
        query.setSingleLine(true);
        query.setHint(t(lang, "ابحث في نص الكتاب المقدس", "Search the Bible text", "Ἀναζήτηση στὸ κείμενο τῆς Γραφῆς"));
        query.setTextColor(ui.colors().primaryText());
        query.setHintTextColor(ui.colors().secondaryText());
        query.setTextSize(16 * preferences.fontScale());
        query.setPadding(ui.dp(12),ui.dp(8),ui.dp(12),ui.dp(8));
        query.setBackground(ui.round(ui.colors().card(), com.orthodoxprayers.privateapp.ui.ThemePalette.GOLD, 12));
        add(page.root, query, 4, 6);
        Button search = ui.button(t(lang,"بحث","Search","Ἀναζήτηση"), false);
        add(page.root, search, 0, 8);
        LinearLayout results = new LinearLayout(host.activity()); results.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(results, new LinearLayout.LayoutParams(-1,-2));
        LinearLayout books = new LinearLayout(host.activity()); books.setOrientation(LinearLayout.VERTICAL);
        page.root.addView(books, new LinearLayout.LayoutParams(-1,-2));

        Runnable doSearch = () -> {
            String value = query.getText().toString().trim();
            if (value.isEmpty()) return;
            results.removeAllViews();
            results.addView(centered(t(lang,"جارٍ البحث…","Searching…","Ἀναζήτηση…"),14,ui.colors().secondaryText(),false));
            new Thread(() -> {
                try {
                    List<BibleCorpusRepository.SearchHit> hits = bible.search(lang, value, 80);
                    results.post(() -> {
                        results.removeAllViews();
                        if (hits.isEmpty()) {
                            add(results, centered(t(lang,"لا توجد نتائج.","No results.","Δὲν βρέθηκαν ἀποτελέσματα."),14,ui.colors().secondaryText(),false), 8, 8);
                            return;
                        }
                        for (BibleCorpusRepository.SearchHit hit : hits) {
                            LinearLayout card = ui.card();
                            card.addView(ui.text(BibleBookNames.name(hit.book,lang)+" "+hit.chapter+":"+hit.verse,16,ui.colors().accentText(),true));
                            card.addView(ui.text(hit.text,14,ui.colors().primaryText(),false),ui.margins(-1,-2,0,4,0,0));
                            card.setOnClickListener(v -> host.navigate("bible_chapter", hit.book+":"+hit.chapter));
                            add(results,card,2,6);
                        }
                    });
                } catch (Exception error) {
                    results.post(() -> { results.removeAllViews(); add(results, centered(unavailable(lang),14,ui.colors().secondaryText(),false),8,8); });
                }
            }, "BibleSearch").start();
        };
        search.setOnClickListener(v -> doSearch.run());
        query.setOnEditorActionListener((v,a,e)->{ doSearch.run(); return true; });

        books.addView(ui.sectionTitle(t(lang,"الأسفار","Books","Βιβλία")));
        books.addView(centered(t(lang,"جارٍ تحميل قائمة الأسفار…","Loading books…","Φόρτωση βιβλίων…"),14,ui.colors().secondaryText(),false));
        new Thread(() -> {
            try {
                List<BibleCorpusRepository.BookInfo> list = bible.books(lang);
                books.post(() -> {
                    books.removeAllViews();
                    books.addView(ui.sectionTitle(t(lang,"الأسفار","Books","Βιβλία")));
                    for (BibleCorpusRepository.BookInfo book : list) {
                        LinearLayout card = ui.actionCard(com.orthodoxprayers.privateapp.R.drawable.ic_action_readings,
                                BibleBookNames.name(book.code,lang),
                                t(lang,"عدد الأصحاحات: ","Chapters: ","Κεφάλαια: ")+book.chapterCount);
                        card.setOnClickListener(v -> host.navigate("bible_book", book.code));
                        add(books,card,2,6);
                    }
                });
            } catch (Exception error) {
                books.post(() -> { books.removeAllViews(); add(books,centered(unavailable(lang),14,ui.colors().secondaryText(),false),10,10); });
            }
        }, "BibleBooks").start();
        return page.scroll;
    }

    private String sourceLabel(String lang) {
        if ("ar".equals(lang)) return "فان دايك — ملكية عامة";
        if ("el".equals(lang)) return "Ο΄ Brenton + Πατριαρχικὸ Κείμενο 1904 — public domain";
        return "World English Bible British + Deuterocanon — Public Domain";
    }
    private String unavailable(String l) { return t(l,"لم تُضمَّن ملفات الكتاب الكامل في هذا البناء.","The full Bible corpus was not bundled in this build.","Τὸ πλήρες σώμα τῆς Γραφῆς δὲν συμπεριλήφθηκε σὲ αὐτὴν τὴν κατασκευή."); }
    private static String t(String l,String ar,String en,String el){ return "ar".equals(l)?ar:("el".equals(l)?el:en); }
}
