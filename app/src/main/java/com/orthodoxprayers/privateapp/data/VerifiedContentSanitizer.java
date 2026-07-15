package com.orthodoxprayers.privateapp.data;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * Removes any Scripture native-language text that is not independently verified.
 *
 * Signed legacy payloads can remain trusted as signed bytes while unsafe native-language
 * fields are suppressed in memory before display. New payloads should already ship with
 * empty unverified translation fields, but this remains a defense-in-depth layer.
 */
public final class VerifiedContentSanitizer {
    private static final String VERIFIED_STATUS = "VERIFIED_EXACT_NATIVE_SOURCE";

    private VerifiedContentSanitizer() {}


    /**
     * Returns the first unsafe native-language field, or an empty string when the
     * payload is safe to persist. New signed payloads are rejected rather than
     * silently retaining mislabeled or unverified Scripture on disk.
     */
    public static String firstUnsafeTranslationError(JSONObject root) {
        if (root == null) return "payload_empty";
        // Do not reject an otherwise valid signed day because a display-only
        // localized field uses the wrong script. DataRepository.localizedValue()
        // already hides such a field and shows the language-specific unavailable
        // message. Rejecting the whole signed payload here made harmless metadata
        // and partial translations block every daily update.
        String readingError = findUnsafeReading(root.optJSONArray("readings"), "readings");
        if (!readingError.isEmpty()) return readingError;
        JSONObject integrityInputs = root.optJSONObject("integrity_inputs");
        JSONObject nextSunday = integrityInputs == null ? null : integrityInputs.optJSONObject("next_sunday");
        return findUnsafeReading(
                nextSunday == null ? null : nextSunday.optJSONArray("readings"),
                "integrity_inputs.next_sunday.readings"
        );
    }

    private static String findUnsafeReading(JSONArray readings, String pointer) {
        if (readings == null) return "";
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null || !reading.optBoolean("translation_locked", false)) continue;
            String kind = reading.optString("kind", "");
            if (!"epistle".equals(kind) && !"gospel".equals(kind) && !"prokeimenon".equals(kind)) continue;
            JSONObject body = reading.optJSONObject("body");
            if (body == null) continue;
            for (String language : new String[]{"ar", "en", "el"}) {
                String text = body.optString(language, "").trim();
                if (!text.isEmpty() && !isVerifiedNativeText(reading, language, text)) {
                    return "unverified_scripture_native_text:" + pointer + "[" + i + "].body." + language;
                }
            }
        }
        return "";
    }

    public static void sanitize(JSONObject root) {
        if (root == null) return;
        ArrayList<LockedBody> lockedBodies = new ArrayList<>();
        sanitizeReadings(root.optJSONArray("readings"), lockedBodies);

        JSONObject integrityInputs = root.optJSONObject("integrity_inputs");
        JSONObject nextSunday = integrityInputs == null ? null : integrityInputs.optJSONObject("next_sunday");
        sanitizeReadings(nextSunday == null ? null : nextSunday.optJSONArray("readings"), lockedBodies);

        sanitizeServices(root.optJSONArray("services"), lockedBodies);
    }

    private static void sanitizeReadings(JSONArray readings, List<LockedBody> lockedBodies) {
        if (readings == null) return;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null || !reading.optBoolean("translation_locked", false)) continue;
            String kind = reading.optString("kind", "");
            if (!"epistle".equals(kind) && !"gospel".equals(kind) && !"prokeimenon".equals(kind)) continue;

            JSONObject body = reading.optJSONObject("body");
            if (body == null) continue;
            String verifiedArabic = "";
            String verifiedEnglish = "";
            String verifiedGreek = "";
            for (String language : new String[]{"ar", "en", "el"}) {
                String text = body.optString(language, "").trim();
                if (!text.isEmpty() && isVerifiedNativeText(reading, language, text)) {
                    if ("ar".equals(language)) verifiedArabic = text;
                    else if ("en".equals(language)) verifiedEnglish = text;
                    else verifiedGreek = text;
                } else if (!text.isEmpty()) {
                    putQuietly(body, language, "");
                }
            }
            if (!verifiedArabic.isEmpty()) lockedBodies.add(new LockedBody(verifiedArabic, verifiedEnglish, verifiedGreek));
        }
    }

    private static boolean isVerifiedNativeText(JSONObject reading, String language, String text) {
        JSONObject verification = reading.optJSONObject("native_source_verification");
        JSONObject languageVerification = verification == null ? null : verification.optJSONObject(language);
        if (languageVerification == null) return false;
        String status = languageVerification.optString("status", "");
        if (!VERIFIED_STATUS.equals(status)
                && !"IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(status)
                && !"IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS".equals(status)) return false;
        String expectedHash = languageVerification.optString("text_sha256", "").trim();
        if (expectedHash.isEmpty() || !expectedHash.equalsIgnoreCase(sha256(text))) return false;
        if (languageVerification.optBoolean("ai_translation_used", true)) return false;
        if (languageVerification.optBoolean("automatic_diacritization_used", true)) return false;
        if (languageVerification.optString("source_id", "").trim().isEmpty()) return false;
        return matchesLanguageScript(language, text);
    }


    private static boolean matchesLanguageScript(String language, String text) {
        boolean hasLatin = false;
        boolean hasGreek = false;
        boolean hasArabic = false;
        for (int offset = 0; offset < text.length();) {
            int codePoint = text.codePointAt(offset);
            Character.UnicodeScript script = Character.UnicodeScript.of(codePoint);
            if (script == Character.UnicodeScript.LATIN) hasLatin = true;
            else if (script == Character.UnicodeScript.GREEK) hasGreek = true;
            else if (script == Character.UnicodeScript.ARABIC) hasArabic = true;
            offset += Character.charCount(codePoint);
        }
        if ("ar".equals(language)) return hasArabic && !hasGreek;
        if (hasArabic) return false;
        if ("en".equals(language)) return hasLatin && !hasGreek;
        if ("el".equals(language)) return hasGreek;
        return false;
    }

    private static void sanitizeServices(JSONArray services, List<LockedBody> lockedBodies) {
        if (services == null || lockedBodies.isEmpty()) return;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service != null) sanitizeObject(service, lockedBodies);
        }
    }

    private static void sanitizeObject(JSONObject object, List<LockedBody> lockedBodies) {
        if (TranslationCoverage.isLocalizedTextObject(object)) {
            String arabic = object.optString("ar", "");
            LockedBody locked = findLockedBody(arabic, lockedBodies);
            if (locked != null) {
                sanitizeLocalizedTranslation(object, "en", locked.english);
                sanitizeLocalizedTranslation(object, "el", locked.greek);
                return;
            }
        }

        Iterator<String> keys = object.keys();
        while (keys.hasNext()) {
            Object value = object.opt(keys.next());
            if (value instanceof JSONObject) sanitizeObject((JSONObject) value, lockedBodies);
            else if (value instanceof JSONArray) sanitizeArray((JSONArray) value, lockedBodies);
        }
    }

    private static void sanitizeArray(JSONArray array, List<LockedBody> lockedBodies) {
        for (int i = 0; i < array.length(); i++) {
            Object value = array.opt(i);
            if (value instanceof JSONObject) sanitizeObject((JSONObject) value, lockedBodies);
            else if (value instanceof JSONArray) sanitizeArray((JSONArray) value, lockedBodies);
        }
    }

    private static LockedBody findLockedBody(String value, List<LockedBody> bodies) {
        if (value == null || value.isEmpty()) return null;
        for (LockedBody body : bodies) {
            if (value.contains(body.arabic)) return body;
        }
        return null;
    }

    private static void sanitizeLocalizedTranslation(JSONObject object, String language, String verifiedBody) {
        String rendered = object.optString(language, "").trim();
        if (rendered.isEmpty()) return;
        if (verifiedBody == null || verifiedBody.isEmpty() || !rendered.contains(verifiedBody)) {
            putQuietly(object, language, "");
        }
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder(digest.length * 2);
            for (byte item : digest) out.append(String.format("%02x", item & 0xff));
            return out.toString();
        } catch (Exception error) {
            return "";
        }
    }

    private static void putQuietly(JSONObject object, String key, String value) {
        try { object.put(key, value); }
        catch (Exception ignored) {}
    }

    private static final class LockedBody {
        final String arabic;
        final String english;
        final String greek;

        LockedBody(String arabic, String english, String greek) {
            this.arabic = arabic;
            this.english = english == null ? "" : english;
            this.greek = greek == null ? "" : greek;
        }
    }
}
