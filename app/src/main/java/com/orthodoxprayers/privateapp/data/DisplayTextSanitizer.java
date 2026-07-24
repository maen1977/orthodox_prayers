package com.orthodoxprayers.privateapp.data;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Removes non-text USFM character markup from an already verified source text.
 *
 * <p>The detached signature and per-passage SHA-256 are checked against the raw
 * downloaded value before this display-only formatting step. This class never
 * translates, paraphrases or changes a source word.</p>
 */
public final class DisplayTextSanitizer {
    private static final Pattern WORD_MARKER = Pattern.compile(
            "\\\\\\+?w\\s+([^|\\\\]+?)(?:\\|[^\\\\]*?)?\\\\\\+?w\\*"
    );
    private static final Pattern MULTISPACE = Pattern.compile("[ \\t\\u00a0]+");

    private DisplayTextSanitizer() {}

    public static String sanitize(String value) {
        if (value == null || value.isEmpty() || value.indexOf('\\') < 0) {
            return value == null ? "" : value;
        }
        String text = value;
        String previous;
        do {
            previous = text;
            Matcher matcher = WORD_MARKER.matcher(text);
            text = matcher.replaceAll("$1");
        } while (!previous.equals(text));
        return MULTISPACE.matcher(text).replaceAll(" ").trim();
    }
}
