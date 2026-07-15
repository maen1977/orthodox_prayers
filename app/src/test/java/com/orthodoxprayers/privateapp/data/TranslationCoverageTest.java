package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.json.JSONObject;
import org.junit.Test;

public final class TranslationCoverageTest {
    @Test
    public void rejectsArabicCopiedIntoEnglishOrGreekFields() {
        String arabic = "هذا نص عربي موثوق";
        assertFalse(TranslationCoverage.isValidTargetText(arabic, arabic, "en"));
        assertFalse(TranslationCoverage.isValidTargetText(arabic, arabic, "el"));
    }

    @Test
    public void doesNotCountLanguageIndexedMetadataAsLocalizedText() throws Exception {
        JSONObject root = new JSONObject()
                .put("language_sources", new JSONObject()
                        .put("ar", new JSONObject().put("priority", "orthodox_jordan"))
                        .put("en", new JSONObject().put("priority", "goarch"))
                        .put("el", new JSONObject().put("priority", "ecclesia")))
                .put("title", new JSONObject()
                        .put("ar", "عنوان")
                        .put("en", "Title")
                        .put("el", "Τίτλος"));

        TranslationCoverage.Result result = TranslationCoverage.measure(root, "en");

        assertEquals(1, result.total);
        assertEquals(1, result.translated);
    }

    @Test
    public void acceptsTextWrittenInTheRequestedScript() {
        assertTrue(TranslationCoverage.isValidTargetText("Verified English text", "نص عربي", "en"));
        assertTrue(TranslationCoverage.isValidTargetText("Ἐπαληθευμένο ἑλληνικὸ κείμενο", "نص عربي", "el"));
    }
}
