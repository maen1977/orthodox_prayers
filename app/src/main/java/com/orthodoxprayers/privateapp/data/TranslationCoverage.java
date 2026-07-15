package com.orthodoxprayers.privateapp.data;

import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Iterator;

public final class TranslationCoverage {
    public static final class Result {
        public final int total;
        public final int translated;
        public final int percent;

        Result(int total, int translated) {
            this.total = total;
            this.translated = translated;
            this.percent = total == 0 ? 100 : Math.round((translated * 100f) / total);
        }
    }

    private TranslationCoverage() {}

    public static Result measure(Object root, String targetLanguage) {
        Counter counter = new Counter();
        visit(root, targetLanguage, counter);
        return new Result(counter.total, counter.translated);
    }

    private static void visit(Object value, String language, Counter counter) {
        if (value instanceof JSONObject) {
            JSONObject object = (JSONObject) value;
            if (isLocalizedTextObject(object)) {
                counter.total++;
                String ar = object.optString("ar", "").trim();
                String target = object.optString(language, "").trim();
                if (isValidTargetText(target, ar, language)) counter.translated++;
                return;
            }
            Iterator<String> keys = object.keys();
            while (keys.hasNext()) visit(object.opt(keys.next()), language, counter);
        } else if (value instanceof JSONArray) {
            JSONArray array = (JSONArray) value;
            for (int i = 0; i < array.length(); i++) visit(array.opt(i), language, counter);
        }
    }


    /**
     * Language-indexed metadata also uses ar/en/el keys, but its values are nested
     * objects rather than text. Only classify a value as localized copy when every
     * present language slot is a string (or JSON null).
     */
    static boolean isLocalizedTextObject(JSONObject object) {
        if (object == null || !object.has("ar") || (!object.has("en") && !object.has("el"))) {
            return false;
        }
        return isTextSlot(object, "ar") && isTextSlot(object, "en") && isTextSlot(object, "el");
    }

    private static boolean isTextSlot(JSONObject object, String key) {
        if (!object.has(key)) return true;
        Object value = object.opt(key);
        return value == null || value == JSONObject.NULL || value instanceof String;
    }

    /** Reject copied Arabic and wrong-script text instead of treating any Latin/Greek letter as a translation. */
    public static boolean isValidTargetText(String target, String arabic, String language) {
        if (target == null || target.trim().isEmpty()) return false;
        String value = target.trim();
        if (arabic != null && !arabic.trim().isEmpty() && value.equals(arabic.trim())) return false;
        if (UiKit.containsArabic(value)) return false;

        ScriptCounts counts = ScriptCounts.of(value);
        if ("en".equals(language)) {
            return counts.latin > 0 && counts.greek <= Math.max(1, counts.latin / 5);
        }
        if ("el".equals(language)) {
            return counts.greek > 0 && counts.latin <= Math.max(4, counts.greek / 3);
        }
        return true;
    }

    private static final class ScriptCounts {
        final int latin;
        final int greek;

        private ScriptCounts(int latin, int greek) {
            this.latin = latin;
            this.greek = greek;
        }

        static ScriptCounts of(String value) {
            int latin = 0;
            int greek = 0;
            for (int offset = 0; offset < value.length();) {
                int codePoint = value.codePointAt(offset);
                offset += Character.charCount(codePoint);
                Character.UnicodeScript script = Character.UnicodeScript.of(codePoint);
                if (script == Character.UnicodeScript.LATIN) latin++;
                else if (script == Character.UnicodeScript.GREEK) greek++;
            }
            return new ScriptCounts(latin, greek);
        }
    }

    private static final class Counter { int total; int translated; }
}
