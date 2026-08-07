package com.orthodoxprayers.privateapp.bible;

import android.content.Context;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Reads verse-per-line Bible corpora bundled in the APK. The files are generated
 * at build time from the redistributable BibleNLP/eBible corpus. No network is
 * used at runtime.
 */
public final class BibleCorpusRepository {
    public static final String ASSET_ROOT = "bible/corpus/";
    public static final String VREF = "vref.txt";
    public static final String ARABIC = "arb-arb-vd.txt";
    public static final String ENGLISH = "eng-eng-webbe.txt";
    public static final String GREEK_OT = "grc-grcbrent.txt";
    public static final String GREEK_NT = "grc-grcbyz.txt";

    private final Context context;

    public BibleCorpusRepository(Context context) {
        this.context = context.getApplicationContext();
    }

    public boolean isBundled() {
        try (BufferedReader ignored = open(VREF)) {
            return true;
        } catch (Exception error) {
            return false;
        }
    }

    public ResolvedPassage resolve(String language, String canonical) throws IOException {
        List<BibleReference> ranges = BibleReference.parseMany(canonical);
        if (ranges.isEmpty()) return null;
        StringBuilder text = new StringBuilder();
        int verseCount = 0;
        try (ParallelReaders readers = openParallel(language)) {
            String refLine;
            while ((refLine = readers.refs.readLine()) != null) {
                String verseText = readers.nextText();
                BibleReference.ParsedVerseRef ref = BibleReference.parseVrefLine(refLine);
                if (ref == null) continue;
                boolean selected = false;
                for (BibleReference range : ranges) {
                    if (range.contains(ref.book, ref.chapter, ref.verse)) {
                        selected = true;
                        break;
                    }
                }
                if (!selected) continue;
                String raw = verseText == null ? "" : verseText.trim();
                if (raw.isEmpty()) return null;
                if ("<range>".equals(raw)) continue;
                if (text.length() > 0) text.append('\n');
                text.append(ref.verse).append(". ").append(raw);
                verseCount++;
            }
        }
        if (verseCount == 0) return null;
        return new ResolvedPassage(text.toString(), sourceId(language), sourceUrl(language), verseCount);
    }

    public Chapter chapter(String language, String book, int chapter) throws IOException {
        ArrayList<Verse> verses = new ArrayList<>();
        try (ParallelReaders readers = openParallel(language)) {
            String refLine;
            while ((refLine = readers.refs.readLine()) != null) {
                String verseText = readers.nextText();
                BibleReference.ParsedVerseRef ref = BibleReference.parseVrefLine(refLine);
                if (ref == null || !book.equals(ref.book) || ref.chapter != chapter) continue;
                String clean = cleanCorpusText(verseText);
                if (!clean.isEmpty()) verses.add(new Verse(ref.book, ref.chapter, ref.verse, clean));
            }
        }
        return new Chapter(book, chapter, verses);
    }

    public List<BookInfo> books(String language) throws IOException {
        LinkedHashMap<String, BookInfo> result = new LinkedHashMap<>();
        try (ParallelReaders readers = openParallel(language)) {
            String refLine;
            while ((refLine = readers.refs.readLine()) != null) {
                String verseText = readers.nextText();
                BibleReference.ParsedVerseRef ref = BibleReference.parseVrefLine(refLine);
                if (ref == null || cleanCorpusText(verseText).isEmpty()) continue;
                BookInfo current = result.get(ref.book);
                if (current == null) result.put(ref.book, new BookInfo(ref.book, ref.chapter));
                else if (ref.chapter > current.chapterCount) current.chapterCount = ref.chapter;
            }
        }
        return new ArrayList<>(result.values());
    }

    public List<SearchHit> search(String language, String query, int limit) throws IOException {
        String needle = normalizeSearch(query);
        if (needle.isEmpty()) return new ArrayList<>();
        int max = Math.max(1, Math.min(200, limit));
        ArrayList<SearchHit> result = new ArrayList<>();
        try (ParallelReaders readers = openParallel(language)) {
            String refLine;
            while ((refLine = readers.refs.readLine()) != null && result.size() < max) {
                String verseText = readers.nextText();
                String clean = cleanCorpusText(verseText);
                if (clean.isEmpty() || !normalizeSearch(clean).contains(needle)) continue;
                BibleReference.ParsedVerseRef ref = BibleReference.parseVrefLine(refLine);
                if (ref != null) result.add(new SearchHit(ref.book, ref.chapter, ref.verse, clean));
            }
        }
        return result;
    }

    private ParallelReaders openParallel(String language) throws IOException {
        BufferedReader refs = open(VREF);
        if ("ar".equals(language)) return new ParallelReaders(refs, open(ARABIC), null);
        if ("el".equals(language)) return new ParallelReaders(refs, open(GREEK_OT), open(GREEK_NT));
        return new ParallelReaders(refs, open(ENGLISH), null);
    }

    private BufferedReader open(String name) throws IOException {
        return new BufferedReader(new InputStreamReader(
                context.getAssets().open(ASSET_ROOT + name), StandardCharsets.UTF_8), 32 * 1024);
    }

    private static String cleanCorpusText(String text) {
        if (text == null) return "";
        String value = text.trim();
        if (value.isEmpty() || "<range>".equals(value)) return "";
        return value;
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
        if ("el".equals(language)) return "https://ebible.org/";
        return "https://ebible.org/eng-webbe/";
    }

    private static final class ParallelReaders implements AutoCloseable {
        final BufferedReader refs;
        final BufferedReader primary;
        final BufferedReader secondary;

        ParallelReaders(BufferedReader refs, BufferedReader primary, BufferedReader secondary) {
            this.refs = refs;
            this.primary = primary;
            this.secondary = secondary;
        }

        String nextText() throws IOException {
            String first = primary.readLine();
            if (secondary == null) return first == null ? "" : first;
            String second = secondary.readLine();
            if (first != null && !first.trim().isEmpty()) return first;
            return second == null ? "" : second;
        }

        @Override public void close() throws IOException {
            IOException failure = null;
            try { refs.close(); } catch (IOException e) { failure = e; }
            try { primary.close(); } catch (IOException e) { if (failure == null) failure = e; }
            if (secondary != null) try { secondary.close(); } catch (IOException e) { if (failure == null) failure = e; }
            if (failure != null) throw failure;
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
