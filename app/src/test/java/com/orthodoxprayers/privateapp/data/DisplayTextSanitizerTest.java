package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public final class DisplayTextSanitizerTest {
    @Test
    public void removesExtendedWordMarkersWithoutChangingWords() {
        String raw = "καὶ \\+w ἐγένετο|lemma=\"γίνομαι\" strong=\"G1096\"\\+w* φῶς";
        assertEquals("καὶ ἐγένετο φῶς", DisplayTextSanitizer.sanitize(raw));
    }

    @Test
    public void removesOrdinaryWordMarkersWithoutChangingWords() {
        String raw = "The \\w Word|lemma=\"λόγος\" strong=\"G3056\"\\w* was God.";
        assertEquals("The Word was God.", DisplayTextSanitizer.sanitize(raw));
    }

    @Test
    public void leavesOrdinaryLiturgicalTextUntouched() {
        String raw = "Κύριε, ἐλέησον.";
        assertEquals(raw, DisplayTextSanitizer.sanitize(raw));
    }
}
