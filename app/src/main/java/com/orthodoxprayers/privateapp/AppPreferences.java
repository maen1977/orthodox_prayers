package com.orthodoxprayers.privateapp;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class AppPreferences {
    private static final String PREFS = "orthodox_prayers_prefs";
    private static final String FAVORITES_LEGACY = "favorites_csv";
    private static final String FAVORITES_SET = "favorites_set_v2";
    private final SharedPreferences values;

    public AppPreferences(Context context) {
        values = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String language() { return values.getString("language", "ar"); }
    public void setLanguage(String value) { values.edit().putString("language", value).apply(); }
    public String effectiveLanguage() { return "ar_original".equals(language()) ? "ar" : language(); }
    public boolean isRtl() { return "ar".equals(effectiveLanguage()); }

    public float fontScale() { return values.getFloat("font_scale", 1.0f); }
    public void setFontScale(float value) { values.edit().putFloat("font_scale", Math.max(0.85f, Math.min(1.65f, value))).apply(); }

    public boolean darkMode() { return values.getBoolean("dark_mode", false); }
    public void setDarkMode(boolean value) { values.edit().putBoolean("dark_mode", value).apply(); }

    public boolean showOriginal() { return values.getBoolean("show_original", false) || "ar_original".equals(language()); }
    public void setShowOriginal(boolean value) { values.edit().putBoolean("show_original", value).apply(); }

    public boolean keepScreenOn() { return values.getBoolean("keep_screen_on", false); }
    public void setKeepScreenOn(boolean value) { values.edit().putBoolean("keep_screen_on", value).apply(); }

    public String legacyCachedTodayJson() { return values.getString("cache_today_json", null); }
    public String cachedEtag(String endpoint) {
        String savedEndpoint = values.getString("cache_today_etag_endpoint", "");
        String requestedEndpoint = endpoint == null ? "" : endpoint.trim();
        if (!requestedEndpoint.equals(savedEndpoint)) return "";
        return values.getString("cache_today_etag", "");
    }
    public long lastSuccessfulUpdate() { return values.getLong("last_successful_update", 0L); }
    public long lastRefreshAttempt() { return values.getLong("last_refresh_attempt", 0L); }
    public boolean lastRefreshSucceeded() { return values.getBoolean("last_refresh_succeeded", false); }
    public String lastRefreshMessage() { return values.getString("last_refresh_message", ""); }

    public void saveRemoteMetadata(String etag, String endpoint, long timestamp) {
        SharedPreferences.Editor editor = values.edit()
                .putLong("last_successful_update", timestamp)
                .putLong("last_refresh_attempt", timestamp)
                .putBoolean("last_refresh_succeeded", true)
                .putString("last_refresh_message", "updated");
        if (etag == null || etag.trim().isEmpty()) {
            editor.remove("cache_today_etag").remove("cache_today_etag_endpoint");
        } else {
            editor.putString("cache_today_etag", etag);
            editor.putString("cache_today_etag_endpoint", endpoint == null ? "" : endpoint.trim());
        }
        editor.remove("cache_today_json").remove("cache_today_signature").apply();
    }

    public void recordRefreshOutcome(boolean succeeded, String message, long timestamp) {
        SharedPreferences.Editor editor = values.edit()
                .putLong("last_refresh_attempt", timestamp)
                .putBoolean("last_refresh_succeeded", succeeded)
                .putString("last_refresh_message", message == null ? "" : message);
        if (succeeded) editor.putLong("last_successful_update", timestamp);
        editor.apply();
    }

    public void clearRemoteMetadata() {
        values.edit().remove("cache_today_etag").remove("cache_today_etag_endpoint").apply();
    }

    public void clearLegacyRemoteCache() {
        values.edit()
                .remove("cache_today_json")
                .remove("cache_today_signature")
                .apply();
    }

    public Set<String> favorites() {
        LinkedHashSet<String> result = new LinkedHashSet<>();
        Set<String> stored = values.getStringSet(FAVORITES_SET, null);
        if (stored != null) {
            for (String item : stored) {
                String id = item == null ? "" : item.trim();
                if (!id.isEmpty()) result.add(id);
            }
            return result;
        }

        // One-time migration from the old comma-separated representation.
        String csv = values.getString(FAVORITES_LEGACY, "");
        if (csv != null && !csv.trim().isEmpty()) {
            for (String item : csv.split(",")) {
                String id = item.trim();
                if (!id.isEmpty()) result.add(id);
            }
        }
        values.edit()
                .putStringSet(FAVORITES_SET, new LinkedHashSet<>(result))
                .remove(FAVORITES_LEGACY)
                .apply();
        return result;
    }

    public boolean isFavorite(String id) { return id != null && favorites().contains(id); }

    public void toggleFavorite(String id) {
        if (id == null || id.trim().isEmpty()) return;
        Set<String> current = favorites();
        if (current.contains(id)) current.remove(id); else current.add(id);
        values.edit()
                .putStringSet(FAVORITES_SET, new LinkedHashSet<>(current))
                .remove(FAVORITES_LEGACY)
                .apply();
    }

    public int readerPosition(String serviceId) { return values.getInt("reader_position_" + serviceId, 0); }
    public int readerOffset(String serviceId) { return values.getInt("reader_offset_" + serviceId, 0); }
    public void setReaderPosition(String serviceId, int position) {
        setReaderPosition(serviceId, position, 0);
    }
    public void setReaderPosition(String serviceId, int position, int offset) {
        values.edit()
                .putInt("reader_position_" + serviceId, Math.max(0, position))
                .putInt("reader_offset_" + serviceId, offset)
                .apply();
    }


    public boolean readerControlsExpanded() { return values.getBoolean("reader_controls_expanded", true); }
    public void setReaderControlsExpanded(boolean value) { values.edit().putBoolean("reader_controls_expanded", value).apply(); }

    public void migrateReaderLayoutState(int targetVersion) {
        int currentVersion = values.getInt("reader_layout_version", 0);
        if (currentVersion >= targetVersion) return;
        SharedPreferences.Editor editor = values.edit();
        for (String key : values.getAll().keySet()) {
            if (key.startsWith("reader_position_") || key.startsWith("reader_offset_")) {
                editor.remove(key);
            }
        }
        editor.putInt("reader_layout_version", targetVersion).apply();
    }

    public String lastSearchQuery() { return values.getString("last_search_query", ""); }
    public void setLastSearchQuery(String value) { values.edit().putString("last_search_query", value == null ? "" : value).apply(); }
    public float lineSpacingMultiplier() { return values.getFloat("line_spacing_multiplier", 1.16f); }
    public void setLineSpacingMultiplier(float value) {
        values.edit().putFloat("line_spacing_multiplier", Math.max(1.0f, Math.min(1.65f, value))).apply();
    }

    public String fontFamily() { return values.getString("font_family", "sans"); }
    public void setFontFamily(String value) {
        String safe = "serif".equals(value) || "monospace".equals(value) ? value : "sans";
        values.edit().putString("font_family", safe).apply();
    }

    /** 0 disables auto-scroll; 1..4 are progressively faster reader speeds. */
    public int autoScrollSpeed() { return Math.max(0, Math.min(4, values.getInt("auto_scroll_speed", 0))); }
    public void setAutoScrollSpeed(int value) { values.edit().putInt("auto_scroll_speed", Math.max(0, Math.min(4, value))).apply(); }

    public String calendarMode() { return values.getString("calendar_mode", "gregorian"); }
    public void setCalendarMode(String value) {
        values.edit().putString("calendar_mode", "julian".equals(value) ? "julian" : "gregorian").apply();
    }

    public boolean remindersEnabled(String kind) { return values.getBoolean("reminder_" + kind + "_enabled", false); }
    public void setRemindersEnabled(String kind, boolean value) { values.edit().putBoolean("reminder_" + kind + "_enabled", value).apply(); }
    public int reminderMinuteOfDay(String kind, int fallback) {
        return Math.max(0, Math.min(1439, values.getInt("reminder_" + kind + "_minute", fallback)));
    }
    public void setReminderMinuteOfDay(String kind, int minuteOfDay) {
        values.edit().putInt("reminder_" + kind + "_minute", Math.max(0, Math.min(1439, minuteOfDay))).apply();
    }
    public String pendingReminderKind() { return values.getString("pending_reminder_kind", ""); }
    public void setPendingReminderKind(String kind) { values.edit().putString("pending_reminder_kind", kind == null ? "" : kind).apply(); }
    public void clearPendingReminderKind() { values.edit().remove("pending_reminder_kind").apply(); }

    public Set<String> pinnedServices() {
        Set<String> stored = values.getStringSet("pinned_services", null);
        return stored == null ? new LinkedHashSet<>() : new LinkedHashSet<>(stored);
    }
    public boolean isPinned(String serviceId) { return serviceId != null && pinnedServices().contains(serviceId); }
    public void togglePinned(String serviceId) {
        if (serviceId == null || serviceId.trim().isEmpty()) return;
        Set<String> current = pinnedServices();
        if (current.contains(serviceId)) current.remove(serviceId); else current.add(serviceId);
        values.edit().putStringSet("pinned_services", new LinkedHashSet<>(current)).apply();
    }

    public List<String> recentServices() { return readStringList("recent_services_json"); }
    public void recordRecentService(String serviceId) {
        if (serviceId == null || serviceId.trim().isEmpty()) return;
        List<String> items = recentServices();
        items.remove(serviceId);
        items.add(0, serviceId);
        while (items.size() > 20) items.remove(items.size() - 1);
        writeStringList("recent_services_json", items);
    }
    public void clearRecentServices() { values.edit().remove("recent_services_json").apply(); }

    public List<String> favoriteOrder() {
        List<String> ordered = readStringList("favorite_order_json");
        Set<String> current = favorites();
        ordered.removeIf(id -> !current.contains(id));
        for (String id : current) if (!ordered.contains(id)) ordered.add(id);
        return ordered;
    }
    public void moveFavorite(String serviceId, int delta) {
        List<String> ordered = favoriteOrder();
        int from = ordered.indexOf(serviceId);
        if (from < 0) return;
        int to = Math.max(0, Math.min(ordered.size() - 1, from + delta));
        if (to == from) return;
        ordered.remove(from);
        ordered.add(to, serviceId);
        writeStringList("favorite_order_json", ordered);
    }

    public String favoriteFolder(String serviceId) {
        try {
            return new JSONObject(values.getString("favorite_folders_json", "{}")).optString(serviceId, "default");
        } catch (Exception ignored) { return "default"; }
    }
    public void setFavoriteFolder(String serviceId, String folder) {
        if (serviceId == null || serviceId.trim().isEmpty()) return;
        try {
            JSONObject object = new JSONObject(values.getString("favorite_folders_json", "{}"));
            object.put(serviceId, folder == null || folder.trim().isEmpty() ? "default" : folder);
            values.edit().putString("favorite_folders_json", object.toString()).apply();
        } catch (Exception ignored) {}
    }

    public Set<String> offlineLanguages() {
        Set<String> stored = values.getStringSet("offline_languages", null);
        if (stored == null) {
            LinkedHashSet<String> defaults = new LinkedHashSet<>();
            defaults.add("ar"); defaults.add("en"); defaults.add("el");
            return defaults;
        }
        return new LinkedHashSet<>(stored);
    }
    public boolean offlineLanguageEnabled(String language) { return offlineLanguages().contains(language); }
    public void setOfflineLanguageEnabled(String language, boolean enabled) {
        if (!"ar".equals(language) && !"en".equals(language) && !"el".equals(language)) return;
        if (!enabled && language.equals(effectiveLanguage())) return;
        Set<String> current = offlineLanguages();
        if (enabled) current.add(language); else current.remove(language);
        if (current.isEmpty()) current.add(effectiveLanguage());
        values.edit().putStringSet("offline_languages", new LinkedHashSet<>(current)).apply();
    }

    private List<String> readStringList(String key) {
        ArrayList<String> result = new ArrayList<>();
        try {
            JSONArray array = new JSONArray(values.getString(key, "[]"));
            for (int i = 0; i < array.length(); i++) {
                String item = array.optString(i, "").trim();
                if (!item.isEmpty() && !result.contains(item)) result.add(item);
            }
        } catch (Exception ignored) {}
        return result;
    }

    private void writeStringList(String key, List<String> items) {
        JSONArray array = new JSONArray();
        for (String item : items) if (item != null && !item.trim().isEmpty()) array.put(item);
        values.edit().putString(key, array.toString()).apply();
    }

}
