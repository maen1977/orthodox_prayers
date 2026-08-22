package com.orthodoxprayers.privateapp.data;

import com.orthodoxprayers.privateapp.model.LocalizedValue;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Locale;

/**
 * One fail-closed display rule for commemorations.
 *
 * <p>A verified, non-empty commemoration is shown. Pending, unavailable, generic,
 * or whitespace-only values are treated as absent so the UI never invents a
 * commemoration card, notification, or widget line.</p>
 */
public final class CommemorationDisplayPolicy {
    private CommemorationDisplayPolicy() {}

    public interface Localizer {
        LocalizedValue localizedValue(JSONObject value, String fallback);
    }

    public static String displayText(JSONObject day, Localizer localizer) {
        if (day == null || localizer == null) return "";

        JSONObject localCommemoration = day.optJSONObject("local_commemoration");
        String local = displayObject(
                localCommemoration,
                firstStatus(day, "local_commemoration_status", localCommemoration),
                localizer
        );
        if (!local.isEmpty()) return local;

        JSONObject commemoration = day.optJSONObject("commemoration");
        String standard = displayObject(
                commemoration,
                firstStatus(day, "commemoration_status", commemoration),
                localizer
        );
        if (!standard.isEmpty()) return standard;

        String occasions = displayOccasions(day.optJSONArray("occasions"), localizer);
        if (!occasions.isEmpty()) return occasions;

        String occasionStatus = day.optString("occasion_status", "");
        if (isUnavailableStatus(occasionStatus)) return "";

        String feast = clean(localizedText(localizer, day.optJSONObject("feast")));
        if (isDisplayableText(feast)) return feast;

        String note = clean(localizedText(localizer, day.optJSONObject("note")));
        return isDisplayableText(note) ? note : "";
    }

    private static String displayOccasions(JSONArray values, Localizer localizer) {
        if (values == null || localizer == null) return "";
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < values.length(); i++) {
            JSONObject occasion = values.optJSONObject(i);
            if (occasion == null) continue;
            String title = clean(localizedText(localizer, occasion.optJSONObject("title")));
            if (!isDisplayableText(title)) continue;
            if (result.length() > 0) result.append("\n");
            result.append(title);
        }
        return result.toString();
    }

    public static boolean isDisplayableText(String value) {
        String text = clean(value);
        if (text.isEmpty()) return false;
        String folded = text.toLowerCase(Locale.ROOT);
        return !folded.contains("تذكار اليوم بحسب التقويم الكنسي القديم")
                && !folded.contains("تعذّر التحقق من تذكار هذا اليوم")
                && !folded.contains("تعذر التحقق من تذكار هذا اليوم")
                && !folded.contains("this day’s commemoration could not be verified")
                && !folded.contains("this day's commemoration could not be verified")
                && !folded.contains("ἡ μνήμη τῆς ἡμέρας δὲν κατέστη δυνατόν")
                && !folded.contains("تذكار اليوم يُستكمل من التحديث الموثق")
                && !folded.contains("تذكار اليوم يستكمل من التحديث الموثق")
                && !folded.contains("daily commemoration is completed by the verified update")
                && !folded.contains("today’s commemoration according to the old church calendar")
                && !folded.contains("today's commemoration according to the old church calendar")
                && !folded.contains("daily commemoration according to the old ecclesiastical calendar")
                && !folded.contains("daily commemoration according to the old church calendar")
                && !folded.contains("ἡ μνήμη τῆς ἡμέρας συμπληρώνεται")
                && !folded.contains("ἡ σημερινὴ μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο")
                && !folded.contains("μνήμη τῆς ἡμέρας κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο");
    }

    public static boolean isUnavailableStatus(String value) {
        String status = clean(value).toUpperCase(Locale.ROOT);
        return status.startsWith("UNAVAILABLE")
                || status.startsWith("PENDING")
                || status.startsWith("NO_VERIFIED")
                || status.startsWith("MISSING")
                || status.startsWith("REJECTED")
                || status.startsWith("BLOCKED");
    }

    private static String displayObject(JSONObject value, String status, Localizer localizer) {
        if (value == null || isUnavailableStatus(status)) return "";
        String title = clean(localizedText(localizer, value.optJSONObject("title")));
        if (title.isEmpty()) {
            title = clean(localizedText(localizer, value.optJSONObject("name")));
        }
        return isDisplayableText(title) ? title : "";
    }

    private static String firstStatus(JSONObject day, String dayKey, JSONObject value) {
        String status = day.optString(dayKey, "");
        if (status.trim().isEmpty() && value != null) status = value.optString("status", "");
        return status;
    }

    private static String localizedText(Localizer localizer, JSONObject value) {
        LocalizedValue localized = localizer.localizedValue(value, "");
        if (localized == null || localized.translationUnavailable) return "";
        return localized.text;
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }
}
