package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class TranslationCoverageTest {
    @Test
    public void rejectsArabicCopiedIntoEnglishOrGreekFields() {
        String arabic = "هذا نص عربي موثوق";
        assertFalse(TranslationCoverage.isValidTargetText(arabic, arabic, "en"));
        assertFalse(TranslationCoverage.isValidTargetText(arabic, arabic, "el"));
    }

    @Test
    public void acceptsTextWrittenInTheRequestedScript() {
        assertTrue(TranslationCoverage.isValidTargetText("Verified English text", "نص عربي", "en"));
        assertTrue(TranslationCoverage.isValidTargetText("Ἐπαληθευμένο ἑλληνικὸ κείμενο", "نص عربي", "el"));
    }
}
