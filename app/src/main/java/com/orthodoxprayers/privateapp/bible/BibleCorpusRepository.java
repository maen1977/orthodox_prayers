package com.orthodoxprayers.privateapp.bible;

import android.content.Context;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;

/**
 * Reads reference-aware Bible TSV files bundled in the APK. The files are
 * generated at build time from redistributable public-domain eBible USFM
 * archives. No network is used at runtime.
 */
public final class BibleCorpusRepository {
    public static final String ASSET_ROOT = "bible/corpus/";
    public static final String ARABIC = "arb-arb-vd.tsv";
    public static final String ENGLISH = "eng-eng-webbe.tsv";
    public static final String GREEK_OT = "grc-grcbrent.tsv";
    public static final String GREEK_NT = "grc-grcbyz.tsv";

    private final Context context;

    public BibleCorpusRepository(Context context) {
        this.context = context.getApplicationContext();
    }

    public boolean isBundled() {
        for (String file : new String[] {ARABIC, ENGLISH, GREEK_OT, GREEK_NT}) {
            try (BufferedReader ignored = open(file)) {
                // Continue until every required corpus is proven present.
            } catch (Exception error) {
                return false;
            }
        }
        return true;
    }

    public ResolvedPassage resolve(String language, String canonical) throws IOException {
        List<BibleReference> ranges = BibleReference.parseMany(canonical);
        if (ranges.isEmpty()) return null;
        StringBuilder text = new StringBuilder();
        int verseCount = 0;
        for (String file : filesForLanguage(language)) {
            try (BufferedReader reader = open(file)) {
                String line;
                while ((line = reader.readLine()) != null) {
                    CorpusVerse verse = parseCorpusLine(line);
                    if (verse == null) continue;
                    boolean selected = false;
                    for (BibleReference range : ranges) {
                        if (range.contains(verse.book, verse.chapter, verse.verse)) {
                            selected = true;
                            break;
                        }
                    }
                    if (!selected || verse.text.isEmpty() || "<range>".equals(verse.text)) continue;
                    if (text.length() > 0) text.append('\n');
                    text.append(verse.verse).append(". ").append(verse.text);
                    verseCount++;
                }
            }
        }
        if (verseCount == 0) return null;
        return new ResolvedPassage(text.toString(), sourceId(language), sourceUrl(language), verseCount);
    }

    public Chapter chapter(String language, String book, int chapter) throws IOException {
        ArrayList<Verse> verses = new ArrayList<>();
        for (String file : filesForLanguage(language)) {
            try (BufferedReader reader = open(file)) {
                String line;
                while ((line = reader.readLine()) != null) {
                    CorpusVerse verse = parseCorpusLine(line);
                    if (verse == null || !book.equals(verse.book) || verse.chapter != chapter) continue;
                    if (!verse.text.isEmpty() && !"<range>".equals(verse.text)) {
                        verses.add(new Verse(verse.book, verse.chapter, verse.verse, verse.text));
                    }
                }
            }
        }
        return new Chapter(book, chapter, verses);
    }

    public List<BookInfo> books(String language) throws IOException {
        LinkedHashMap<String, BookInfo> result = new LinkedHashMap<>();
        for (String file : filesForLanguage(language)) {
            try (BufferedReader reader = open(file)) {
                String line;
                while ((line = reader.readLine()) != null) {
                    CorpusVerse verse = parseCorpusLine(line);
                    if (verse == null || verse.text.isEmpty() || "<range>".equals(verse.text)) continue;
                    BookInfo current = result.get(verse.book);
                    if (current == null) result.put(verse.book, new BookInfo(verse.book, verse.chapter));
                    else if (verse.chapter > current.chapterCount) current.chapterCount = verse.chapter;
                }
            }
        }
        return new ArrayList<>(result.values());
    }

    public List<SearchHit> search(String language, String query, int limit) throws IOException {
        String needle = normalizeSearch(query);
        if (needle.isEmpty()) return new ArrayList<>();
        int max = Math.max(1, Math.min(200, limit));
        ArrayList<SearchHit> result = new ArrayList<>();
        for (String file : filesForLanguage(language)) {
            if (result.size() >= max) break;
            try (BufferedReader reader = open(file)) {
                String line;
                while ((line = reader.readLine()) != null && result.size() < max) {
                    CorpusVerse verse = parseCorpusLine(line);
                    if (verse == null || verse.text.isEmpty() || "<range>".equals(verse.text)) continue;
                    if (normalizeSearch(verse.text).contains(needle)) {
                        result.add(new SearchHit(verse.book, verse.chapter, verse.verse, verse.text));
                    }
                }
            }
        }
        return result;
    }

    private String[] filesForLanguage(String language) {
        if ("ar".equals(language)) return new String[] {ARABIC};
        if ("el".equals(language)) return new String[] {GREEK_OT, GREEK_NT};
        return new String[] {ENGLISH};
    }

    private BufferedReader open(String name) throws IOException {
        return new BufferedReader(new InputStreamReader(
                context.getAssets().open(ASSET_ROOT + name), StandardCharsets.UTF_8), 32 * 1024);
    }

    private static CorpusVerse parseCorpusLine(String line) {
        if (line == null || line.isEmpty()) return null;
        String[] parts = line.split("\\t", 4);
        if (parts.length != 4) return null;
        try {
            int chapter = Integer.parseInt(parts[1]);
            int verse = Integer.parseInt(parts[2]);
            if (chapter <= 0 || verse <= 0 || parts[0].isEmpty()) return null;
            return new CorpusVerse(parts[0], chapter, verse, parts[3].trim());
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static String normalizeSearch(String value) {
        if (value == null) return "";
        return value.toLowerCase(Locale.ROOT)
                .replace('\u064b', ' ').replace('\u064c', ' ').replace('\u064d', ' ')
                .replace('\u064e', ' ').replace('\u064f', ' ').replace('\u0650', ' ')
                .replace('\u0651', ' ').replace('\u0652', ' ')
                .replaceAll("\\s+", " ").trim();
    }

    public static String sourceId(String language) {
        if ("ar".equals(language)) return "ebible_arabic_van_dyck_full";
        if ("el".equals(language)) return "ebible_greek_lxx_brenton_plus_patriarchal_1904";
        return "ebible_world_english_bible_british_deuterocanon";
    }

    public static String sourceUrl(String language) {
        if ("ar".equals(language)) return "https://ebible.org/arb-vd/";
        if ("el".equals(language)) return "https://ebible.org/grcbrent/ + https://ebible.org/grcbyz/";
        return "https://ebible.org/eng-webbe/";
    }

    private static final class CorpusVerse {
        final String book;
        final int chapter;
        final int verse;
        final String text;
        CorpusVerse(String book, int chapter, int verse, String text) {
            this.book = book;
            this.chapter = chapter;
            this.verse = verse;
            this.text = text;
        }
    }

    public static final class ResolvedPassage {
        public final String text;
        public final String sourceId;
        public final String sourceUrl;
        public final int verseCount;
        ResolvedPassage(String text, String sourceId, String sourceUrl, int verseCount) {
            this.text = text;
            this.sourceId = sourceId;
            this.sourceUrl = sourceUrl;
            this.verseCount = verseCount;
        }
    }

    public static final class Verse {
        public final String book;
        public final int chapter;
        public final int verse;
        public final String text;
        Verse(String book, int chapter, int verse, String text) {
            this.book = book; this.chapter = chapter; this.verse = verse; this.text = text;
        }
    }

    public static final class Chapter {
        public final String book;
        public final int chapter;
        public final List<Verse> verses;
        Chapter(String book, int chapter, List<Verse> verses) {
            this.book = book; this.chapter = chapter; this.verses = verses;
        }
    }

    public static final class BookInfo {
        public final String code;
        public int chapterCount;
        BookInfo(String code, int chapterCount) { this.code = code; this.chapterCount = chapterCount; }
    }

    public static final class SearchHit {
        public final String book;
        public final int chapter;
        public final int verse;
        public final String text;
        SearchHit(String book, int chapter, int verse, String text) {
            this.book = book; this.chapter = chapter; this.verse = verse; this.text = text;
        }
        public String reference() { return book + " " + chapter + ":" + verse; }
    }
}
