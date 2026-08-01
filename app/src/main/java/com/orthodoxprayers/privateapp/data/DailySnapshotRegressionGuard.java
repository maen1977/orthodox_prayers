package com.orthodoxprayers.privateapp.data;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Iterator;

/**
 * Prevents a later same-day publication from deleting already accepted native text.
 *
 * A later corrected signed daily publication may add content, but a temporarily incomplete
 * source response must not replace the valid accepted Epistle, Gospel, Matins Gospel, or
 * Liturgy propers already stored on the device.
 */
public final class DailySnapshotRegressionGuard {
    private static final String[] PROTECTED_READING_KINDS = {
            "matins_gospel", "prokeimenon", "epistle", "gospel"
    };

    private DailySnapshotRegressionGuard() {}

    public static String firstRegression(
            JSONObject accepted,
            JSONObject candidate,
            String language
    ) {
        if (accepted == null || candidate == null) return "";
        String acceptedDate = accepted.optString("date_iso", "");
        String candidateDate = candidate.optString("date_iso", "");
        if (acceptedDate.isEmpty() || !acceptedDate.equals(candidateDate)) return "";

        String lane = language == null ? "" : language.trim();
        if (!"ar".equals(lane) && !"en".equals(lane) && !"el".equals(lane)) return "";

        for (String kind : PROTECTED_READING_KINDS) {
            JSONObject before = readingByKind(accepted.optJSONArray("readings"), kind);
            if (before == null) continue;
            JSONObject after = readingByKind(candidate.optJSONArray("readings"), kind);
            if (lostLocalizedValue(before, after, "reference", lane)) {
                return "same_day_content_regression:" + kind + ":reference";
            }
            if (lostLocalizedValue(before, after, "body", lane)) {
                return "same_day_content_regression:" + kind + ":body";
            }
        }

        JSONObject beforeSlots = liturgySlots(accepted);
        JSONObject afterSlots = liturgySlots(candidate);
        if (beforeSlots != null) {
            Iterator<String> keys = beforeSlots.keys();
            while (keys.hasNext()) {
                String slot = keys.next();
                JSONObject before = beforeSlots.optJSONObject(slot);
                String previous = before == null ? "" : before.optString(lane, "").trim();
                if (previous.isEmpty()) continue;
                JSONObject after = afterSlots == null ? null : afterSlots.optJSONObject(slot);
                String replacement = after == null ? "" : after.optString(lane, "").trim();
                if (replacement.isEmpty()) {
                    return "same_day_content_regression:liturgy_slot:" + slot;
                }
            }
        }
        return "";
    }

    private static boolean lostLocalizedValue(
            JSONObject before,
            JSONObject after,
            String field,
            String language
    ) {
        JSONObject beforeValue = before.optJSONObject(field);
        String previous = beforeValue == null ? "" : beforeValue.optString(language, "").trim();
        if (previous.isEmpty()) return false;
        JSONObject afterValue = after == null ? null : after.optJSONObject(field);
        return afterValue == null || afterValue.optString(language, "").trim().isEmpty();
    }

    private static JSONObject readingByKind(JSONArray readings, String kind) {
        if (readings == null) return null;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading != null && kind.equals(reading.optString("kind", ""))) return reading;
        }
        return null;
    }

    private static JSONObject liturgySlots(JSONObject root) {
        JSONArray services = root.optJSONArray("services");
        if (services == null) return null;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service != null && "divine_liturgy".equals(service.optString("id", ""))) {
                return service.optJSONObject("slot_replacements");
            }
        }
        return null;
    }
}
