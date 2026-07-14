package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public final class VerifiedContentSanitizerTest {
    @Test
    public void stripsUnverifiedReadingAndInjectedServiceTranslations() throws Exception {
        String arabic = "16:13 نص عربي موثق طويل بما يكفي للاختبار";
        JSONObject reading = new JSONObject()
                .put("kind", "gospel")
                .put("translation_locked", true)
                .put("body", new JSONObject()
                        .put("ar", arabic)
                        .put("en", "Wrong English chapter")
                        .put("el", "Wrong English chapter"))
                .put("native_source_verification", new JSONObject()
                        .put("ar", new JSONObject()
                                .put("status", "VERIFIED_EXACT_NATIVE_SOURCE")
                                .put("text_sha256", sha256(arabic))
                                .put("source_id", "orthodox_jordan")
                                .put("ai_translation_used", false)
                                .put("automatic_diacritization_used", false)));
        JSONObject service = new JSONObject().put("segments", new JSONArray().put(
                new JSONObject().put("text", new JSONObject()
                        .put("ar", "متى 16:13-19\n" + arabic)
                        .put("en", "Matthew 16:13-19\nWrong English chapter")
                        .put("el", "Matthew 16:13-19\nWrong English chapter"))
        ));
        JSONObject root = new JSONObject()
                .put("readings", new JSONArray().put(reading))
                .put("services", new JSONArray().put(service));

        VerifiedContentSanitizer.sanitize(root);

        assertEquals("", reading.getJSONObject("body").getString("en"));
        assertEquals("", reading.getJSONObject("body").getString("el"));
        JSONObject text = service.getJSONArray("segments").getJSONObject(0).getJSONObject("text");
        assertEquals("", text.getString("en"));
        assertEquals("", text.getString("el"));
    }

    @Test
    public void retainsIndependentlyVerifiedNativeTextWithMatchingHash() throws Exception {
        String english = "Verified English native-source text";
        JSONObject reading = new JSONObject()
                .put("kind", "epistle")
                .put("translation_locked", true)
                .put("body", new JSONObject().put("ar", "نص عربي").put("en", english).put("el", ""))
                .put("integrity", new JSONObject().put("canonical_reference", "ROM.1.1-2"))
                .put("native_source_verification", new JSONObject()
                        .put("ar", new JSONObject()
                                .put("status", "VERIFIED_EXACT_NATIVE_SOURCE")
                                .put("text_sha256", sha256("نص عربي"))
                                .put("source_id", "orthodox_jordan")
                                .put("ai_translation_used", false)
                                .put("automatic_diacritization_used", false))
                        .put("en", new JSONObject()
                                .put("status", "VERIFIED_EXACT_NATIVE_SOURCE")
                                .put("text_sha256", sha256(english))
                                .put("source_id", "goarch_online_chapel")
                                .put("ai_translation_used", false)
                                .put("automatic_diacritization_used", false)));
        JSONObject serviceText = new JSONObject()
                .put("ar", "رومية 1:1-2\nنص عربي")
                .put("en", "Romans 1:1-2\n" + english)
                .put("el", "Unverified Greek slot");
        JSONObject root = new JSONObject()
                .put("readings", new JSONArray().put(reading))
                .put("services", new JSONArray().put(new JSONObject()
                        .put("segments", new JSONArray().put(new JSONObject().put("text", serviceText)))));

        VerifiedContentSanitizer.sanitize(root);

        assertEquals(english, reading.getJSONObject("body").getString("en"));
        assertEquals("Romans 1:1-2\n" + english, serviceText.getString("en"));
        assertEquals("", serviceText.getString("el"));
    }

    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder out = new StringBuilder();
        for (byte item : digest) out.append(String.format("%02x", item & 0xff));
        return out.toString();
    }
}
