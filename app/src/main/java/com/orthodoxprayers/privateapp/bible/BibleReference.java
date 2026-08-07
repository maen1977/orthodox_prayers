package com.orthodoxprayers.privateapp.bible;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Pure-Java parser for the app's canonical BOOK.C.V-BOOK.C.V notation. */
public final class BibleReference {
    private static final Pattern RANGE = Pattern.compile(
            "^([1-4]?[A-Z0-9]+)\\.(\\d+)\\.(\\d+)-(?:([1-4]?[A-Z0-9]+)\\.)?(?:(\\d+)\\.)?(\\d+)$"
    );
    private static final Pattern SINGLE = Pattern.compile("^([1-4]?[A-Z0-9]+)\\.(\\d+)\\.(\\d+)$");

    public final String book;
    public final int startChapter;
    public final int startVerse;
    public final int endChapter;
    public final int endVerse;

    private BibleReference(String book, int startChapter, int startVerse, int endChapter, int endVerse) {
        this.book = book;
        this.startChapter = startChapter;
        this.startVerse = startVerse;
        this.endChapter = endChapter;
        this.endVerse = endVerse;
    }

    public static List<BibleReference> parseMany(String canonical) {
        if (canonical == null || canonical.trim().isEmpty()) return Collections.emptyList();
        ArrayList<BibleReference> result = new ArrayList<>();
        for (String raw : canonical.split(";")) {
            String part = raw.trim();
            if (part.isEmpty()) continue;
            Matcher single = SINGLE.matcher(part);
            if (single.matches()) {
                String book = single.group(1);
                int chapter = integer(single.group(2));
                int verse = integer(single.group(3));
                result.add(new BibleReference(book, chapter, verse, chapter, verse));
                continue;
            }
            Matcher range = RANGE.matcher(part);
            if (!range.matches()) return Collections.emptyList();
            String startBook = range.group(1);
            String endBook = range.group(4) == null ? startBook : range.group(4);
            if (!startBook.equals(endBook)) return Collections.emptyList();
            int startChapter = integer(range.group(2));
            int startVerse = integer(range.group(3));
            int endChapter = range.group(5) == null ? startChapter : integer(range.group(5));
            int endVerse = integer(range.group(6));
            if (compare(startChapter, startVerse, endChapter, endVerse) > 0) return Collections.emptyList();
            result.add(new BibleReference(startBook, startChapter, startVerse, endChapter, endVerse));
        }
        return result;
    }

    public boolean contains(String candidateBook, int chapter, int verse) {
        if (!book.equals(candidateBook)) return false;
        return compare(chapter, verse, startChapter, startVerse) >= 0
                && compare(chapter, verse, endChapter, endVerse) <= 0;
    }

    public static ParsedVerseRef parseVrefLine(String line) {
        if (line == null) return null;
        String value = line.trim();
        int space = value.indexOf(' ');
        int colon = value.indexOf(':', space + 1);
        if (space <= 0 || colon <= space) return null;
        try {
            return new ParsedVerseRef(
                    value.substring(0, space),
                    Integer.parseInt(value.substring(space + 1, colon)),
                    Integer.parseInt(value.substring(colon + 1))
            );
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private static int integer(String value) {
        return Integer.parseInt(value);
    }

    private static int compare(int chapter, int verse, int otherChapter, int otherVerse) {
        int chapterComparison = Integer.compare(chapter, otherChapter);
        return chapterComparison != 0 ? chapterComparison : Integer.compare(verse, otherVerse);
    }

    public static final class ParsedVerseRef {
        public final String book;
        public final int chapter;
        public final int verse;

        ParsedVerseRef(String book, int chapter, int verse) {
            this.book = book;
            this.chapter = chapter;
            this.verse = verse;
        }

        public String canonicalId() {
            return book + "." + chapter + "." + verse;
        }
    }
}
