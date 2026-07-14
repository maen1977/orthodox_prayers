package com.orthodoxprayers.privateapp;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.LinkedHashSet;
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
    public String cachedEtag() { return values.getString("cache_today_etag", ""); }
    public long lastSuccessfulUpdate() { return values.getLong("last_successful_update", 0L); }
    public long lastRefreshAttempt() { return values.getLong("last_refresh_attempt", 0L); }
    public boolean lastRefreshSucceeded() { return values.getBoolean("last_refresh_succeeded", false); }
    public String lastRefreshMessage() { return values.getString("last_refresh_message", ""); }

    public void saveRemoteMetadata(String etag, long timestamp) {
        SharedPreferences.Editor editor = values.edit()
                .putLong("last_successful_update", timestamp)
                .putLong("last_refresh_attempt", timestamp)
                .putBoolean("last_refresh_succeeded", true)
                .putString("last_refresh_message", "updated");
        if (etag == null || etag.trim().isEmpty()) editor.remove("cache_today_etag");
        else editor.putString("cache_today_etag", etag);
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
        values.edit().remove("cache_today_etag").apply();
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
}
