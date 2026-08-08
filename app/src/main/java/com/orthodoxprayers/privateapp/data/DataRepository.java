package com.orthodoxprayers.privateapp.data;

import android.content.ComponentCallbacks2;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.ui.LocalizedResources;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class DataRepository {
    public enum RefreshResult { UPDATED, NOT_MODIFIED, FAILED }
    public enum RefreshState { IDLE, REFRESHING, UPDATED, CURRENT, FAILED }
    public interface RefreshCallback { void onComplete(RefreshResult result, String message); }

    private static final String TAG = "OrthodoxData";
    private static final int MAX_JSON_BYTES = DataContract.MAX_SIGNED_PAYLOAD_BYTES;
    private static final int MIN_ROLLING_WINDOW_DAYS = 9;
    private static final int MAX_ROLLING_WINDOW_DAYS = 9;
    private static final int MAX_MANIFEST_BYTES = 64_000;
    private static final int MAX_SIGNATURE_BYTES = 16_384;
    private static final int MAX_DOWNLOAD_ATTEMPTS = 2;

    private final Context context;
    private final AppPreferences preferences;
    private DailyDataStore dataStore;
    private final boolean languageScopedStore;
    private final DataSignatureVerifier signatureVerifier;
    private final LocalDailyContentEngine localDailyContentEngine;
    private final LocalDailyCacheStore localDailyCacheStore;
    private final BibleCorpusRepository bibleCorpusRepository;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final Object refreshGuard = new Object();

    private JSONObject today;
    // Language-heavy assets are loaded only for the selected lane. Keeping all
    // three libraries and all three search indexes resident added several MB of
    // avoidable startup memory on low-spec devices. Search remains fully offline
    // but its index is parsed only when the user opens Search.
    private String loadedAssetLanguage = "";
    private JSONObject activeLanguageLibrary;
    private JSONObject activeLanguageSearchIndex;
    private JSONObject sourceRegistry;
    private JSONObject fallbackChurchDirectory;
    private JSONObject fallbackSourceHealth;
    private JSONObject fallbackServiceCoverage;
    private JSONObject religiousCompleteness;
    private JSONObject calendarIndex;
    private int loadedCalendarYear = -1;
    private JSONObject rollingWeekPackage = new JSONObject();
    private final Map<String, JSONObject> calendarByDate = new LinkedHashMap<>();
    private final Map<String, JSONObject> rollingWeekByDate = new LinkedHashMap<>();
    private volatile boolean refreshInProgress;
    private volatile RefreshState refreshState = RefreshState.IDLE;
    private volatile String refreshMessage = "";
    private volatile String loadError = "";
    private volatile String trustSource = "none";
    private volatile String contentHash = "";
    private String loadedStoredSource = "";
    private String loadedStoredHash = "";
    private String loadedEmbeddedHash = "";

    public DataRepository(Context context, AppPreferences preferences) {
        this(context, preferences,
                new DailyDataStore(context, preferences.effectiveLanguage()),
                new DataSignatureVerifier(context), true);
    }

    public DataRepository(Context context, AppPreferences preferences, DailyDataStore dataStore, DataSignatureVerifier signatureVerifier) {
        this(context, preferences, dataStore, signatureVerifier, false);
    }

    private DataRepository(Context context, AppPreferences preferences, DailyDataStore dataStore,
                           DataSignatureVerifier signatureVerifier, boolean languageScopedStore) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        this.dataStore = dataStore;
        this.signatureVerifier = signatureVerifier;
        this.localDailyContentEngine = new LocalDailyContentEngine(this.context);
        this.localDailyCacheStore = new LocalDailyCacheStore(this.context);
        this.bibleCorpusRepository = new BibleCorpusRepository(this.context);
        this.languageScopedStore = languageScopedStore;
        preferences.clearLegacyRemoteCache();
        sourceRegistry = loadJsonAsset("data/source_registry.json");
        fallbackChurchDirectory = loadJsonAsset("data/churches.json");
        fallbackSourceHealth = loadJsonAsset("data/source_health.json");
        fallbackServiceCoverage = loadJsonAsset("data/service_coverage.json");
        religiousCompleteness = loadJsonAsset("data/religious_completeness.json");
        calendarIndex = loadJsonAsset("data/calendar/calendar_index.json");
        // Keep startup light on older devices. The immutable annual calendar is
        // loaded only when a calendar screen or a dated lookup requests it.
        activatePackage(loadBestToday());
        // Never rebuild the nine-day package on the Android main thread. Reuse a
        // previously generated local package when it is still valid; otherwise
        // MainActivity/WorkManager will rebuild it asynchronously after first draw.
        activateCachedLocalPackageIfAvailable();
    }

    private synchronized void loadCalendarYear(int year) {
        if (year == loadedCalendarYear && !calendarByDate.isEmpty()) return;
        JSONObject years = calendarIndex == null ? null : calendarIndex.optJSONObject("years");
        JSONObject metadata = years == null ? null : years.optJSONObject(Integer.toString(year));
        if (metadata == null) return;
        String asset = metadata.optString("asset", "").trim();
        if (asset.isEmpty()) return;
        JSONObject yearPayload = loadJsonAsset(asset);
        JSONArray days = yearPayload.optJSONArray("days");
        if (days == null || days.length() == 0) return;
        calendarByDate.clear();
        for (int i = 0; i < days.length(); i++) {
            JSONObject item = days.optJSONObject(i);
            if (item == null) continue;
            String iso = item.optString("date_iso", item.optString("date", "")).trim();
            if (!iso.isEmpty()) calendarByDate.put(iso, item);
        }
        loadedCalendarYear = year;
    }

    /** Compact offline old-calendar index, loaded one year at a time through 2050. */
    public JSONArray calendarDays() {
        return calendarDays(LocalDate.now(ZoneId.of("Asia/Amman")).getYear());
    }

    public synchronized JSONArray calendarDays(int year) {
        loadCalendarYear(year);
        JSONArray result = new JSONArray();
        for (JSONObject item : calendarByDate.values()) result.put(item);
        return result;
    }

    public JSONObject calendarDay(String date) {
        if (date == null) return null;
        String normalized = date.trim();
        JSONObject complete = rollingWeekByDate.get(normalized);
        if (complete != null) return complete;
        if (normalized.matches("\\d{4}-\\d{2}-\\d{2}")) {
            try {
                loadCalendarYear(Integer.parseInt(normalized.substring(0, 4)));
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return calendarByDate.get(normalized);
    }

    /** The active signed package contains a moving horizon of complete consecutive days. */
    public JSONArray rollingWeekDays() {
        JSONArray result = new JSONArray();
        for (JSONObject day : rollingWeekByDate.values()) result.put(day);
        return result;
    }

    public JSONObject dayData(String date) { return calendarDay(date); }

    public boolean hasCompleteRollingWeek() {
        JSONObject localWindow = rollingWeekPackage.optJSONObject("local_daily_window");
        if (localWindow != null) {
            int dayCount = localWindow.optInt("day_count", 0);
            return !localWindow.optBoolean("network_required", true)
                    && dayCount > 0
                    && rollingWeekByDate.size() == dayCount;
        }
        JSONObject metadata = rollingWeekPackage.optJSONObject("rolling_week");
        if (metadata == null || !isSupportedRollingWindowMetadata(metadata)) return false;
        int dayCount = metadata.optInt("day_count", 0);
        return "COMPLETE".equals(metadata.optString("status", ""))
                && metadata.optBoolean("fail_closed", false)
                && rollingWeekByDate.size() == dayCount;
    }

    private static boolean isSupportedRollingWindowMetadata(JSONObject metadata) {
        int schema = metadata.optInt("schema_version", 0);
        int dayCount = metadata.optInt("day_count", 0);
        String policy = metadata.optString("policy", "");
        if (schema == 1) {
            return dayCount == 9
                    && "NINE_CONSECUTIVE_DAYS_STARTING_TODAY".equals(policy);
        }
        return schema == 2
                && dayCount >= MIN_ROLLING_WINDOW_DAYS
                && dayCount <= MAX_ROLLING_WINDOW_DAYS
                && "ROLLING_FUTURE_WINDOW".equals(policy);
    }

    public String rollingWeekStartDate() {
        JSONObject localWindow = rollingWeekPackage.optJSONObject("local_daily_window");
        if (localWindow != null) return localWindow.optString("start_date", "");
        JSONObject metadata = rollingWeekPackage.optJSONObject("rolling_week");
        return metadata == null ? "" : metadata.optString("start_date", "");
    }

    public String rollingWeekEndDate() {
        JSONObject localWindow = rollingWeekPackage.optJSONObject("local_daily_window");
        if (localWindow != null) return localWindow.optString("end_date", "");
        JSONObject metadata = rollingWeekPackage.optJSONObject("rolling_week");
        return metadata == null ? "" : metadata.optString("end_date", "");
    }

    public int rollingWeekReadyDayCount() { return rollingWeekByDate.size(); }

    public static String datedServiceId(String date, String serviceId) {
        String safeDate = date == null ? "" : date.trim();
        String safeService = serviceId == null ? "" : serviceId.trim();
        return safeDate.matches("\\d{4}-\\d{2}-\\d{2}") && !safeService.isEmpty()
                ? safeDate + "::" + safeService
                : safeService;
    }

    public synchronized JSONObject today() { return today; }
    public JSONObject library() {
        return libraryForLanguage(preferences.effectiveLanguage());
    }

    private synchronized JSONObject libraryForLanguage(String language) {
        ensureLanguageAssets(language, false);
        // Never fall back to another language or to the legacy mixed library.
        // Missing native assets are shown as unavailable rather than substituted.
        return activeLanguageLibrary != null ? activeLanguageLibrary : new JSONObject();
    }

    private synchronized void ensureLanguageAssets(String language, boolean includeSearchIndex) {
        String normalized = normalizeAssetLanguage(language);
        if (!normalized.equals(loadedAssetLanguage)) {
            loadedAssetLanguage = normalized;
            activeLanguageLibrary = loadJsonAsset("data/native/library_" + normalized + ".json");
            applyGeneratedChurchServicePack(activeLanguageLibrary, normalized);
            activeLanguageSearchIndex = null;
        }
        if (includeSearchIndex && activeLanguageSearchIndex == null) {
            activeLanguageSearchIndex = loadJsonAsset("data/search/search_index_" + normalized + ".json");
        }
    }

    private static String normalizeAssetLanguage(String language) {
        if ("en".equals(language)) return "en";
        if ("el".equals(language)) return "el";
        return "ar";
    }

    private synchronized void clearLanguageAssetCache() {
        loadedAssetLanguage = "";
        activeLanguageLibrary = null;
        activeLanguageSearchIndex = null;
    }

    /** Release only reloadable caches; signed current-day data remains resident. */
    public synchronized void releaseOptionalCaches(int level) {
        if (level >= ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW) {
            activeLanguageSearchIndex = null;
        }
        if (level >= ComponentCallbacks2.TRIM_MEMORY_UI_HIDDEN) {
            calendarByDate.clear();
            loadedCalendarYear = 0;
        }
    }
    public String currentAmmanDate() { return LocalDate.now(ZoneId.of("Asia/Amman")).toString(); }
    public boolean isRefreshing() { return refreshInProgress; }
    public RefreshState refreshState() { return refreshState; }
    public String refreshMessage() { return refreshMessage; }
    /** Stable technical code shown in Settings so update failures are diagnosable. */
    public String refreshDiagnosticCode() {
        String code = refreshMessage == null ? "" : refreshMessage.trim();
        if (code.isEmpty()) code = preferences.lastRefreshMessage();
        return code == null || code.trim().isEmpty() ? "none" : code.trim();
    }
    public String loadError() { return loadError; }
    public String trustSource() { return trustSource; }
    public String contentHash() { return contentHash; }
    public String canonicalSourceId() {
        JSONObject integrity = today().optJSONObject("integrity");
        if (integrity == null) return today().optString("native_text_contract", "");
        return integrity.optString("native_text_contract", today().optString("native_text_contract", ""));
    }
    public String sourceNote() { return localized(today().optJSONObject("source_note"), ""); }
    public String selectedOfficialSource() {
        JSONObject publication = today().optJSONObject("publication");
        return publication == null ? "" : publication.optString("selected_source", "");
    }

    public JSONObject sourceRegistry() { return sourceRegistry == null ? new JSONObject() : sourceRegistry; }

    public JSONObject sourceHealth() {
        JSONObject live = today().optJSONObject("source_health");
        return live != null ? live : (fallbackSourceHealth == null ? new JSONObject() : fallbackSourceHealth);
    }

    public JSONObject sourceHealthById(String sourceId) {
        if (sourceId == null || sourceId.trim().isEmpty()) return null;
        JSONArray observations = sourceHealth().optJSONArray("observations");
        if (observations == null) return null;
        JSONObject best = null;
        String normalizedId = sourceId;
        if ("jerusalem_patriarchate_en".equals(sourceId) || "jerusalem_patriarchate_ar".equals(sourceId) || "jerusalem_patriarchate_el".equals(sourceId))
            normalizedId = "jerusalem_patriarchate";
        for (int i = 0; i < observations.length(); i++) {
            JSONObject item = observations.optJSONObject(i);
            if (item == null || !(sourceId.equals(item.optString("source_id")) || normalizedId.equals(item.optString("source_id")))) continue;
            if (best == null || item.optDouble("confidence", 0.0) > best.optDouble("confidence", 0.0)) best = item;
        }
        return best;
    }

    public JSONObject churchDirectory() {
        JSONObject live = today().optJSONObject("church_directory");
        return live != null ? live : (fallbackChurchDirectory == null ? new JSONObject() : fallbackChurchDirectory);
    }

    public JSONArray registeredChurches() {
        JSONArray churches = churchDirectory().optJSONArray("churches");
        return churches == null ? new JSONArray() : churches;
    }

    public JSONArray officialLiveResources() {
        JSONArray resources = churchDirectory().optJSONArray("live_resources");
        return resources == null ? new JSONArray() : resources;
    }

    /** Official dated service links discovered by monitored connectors; no full text is copied. */
    public JSONArray officialServiceLinks() {
        JSONArray result = new JSONArray();
        JSONArray observations = sourceHealth().optJSONArray("observations");
        if (observations == null) return result;
        for (int i = 0; i < observations.length(); i++) {
            JSONObject observation = observations.optJSONObject(i);
            JSONArray links = observation == null ? null : observation.optJSONArray("service_links");
            if (links == null) continue;
            for (int j = 0; j < links.length(); j++) {
                JSONObject source = links.optJSONObject(j);
                if (source == null || !source.optString("url", "").startsWith("https://")) continue;
                JSONObject copy = new JSONObject();
                try {
                    String label = source.optString("title", "Official service");
                    copy.put("id", observation.optString("connector_id", "service") + ":" + j);
                    copy.put("title", new JSONObject().put("ar", label).put("en", label).put("el", label));
                    copy.put("url", source.optString("url"));
                    copy.put("status", source.optString("status", "candidate"));
                    result.put(copy);
                } catch (Exception ignored) { }
            }
        }
        return result;
    }

    /** Metadata is isolated too: never substitute an Arabic/English name in another UI lane. */
    public String metadataLocalized(JSONObject value, String fallback) {
        if (value == null) return fallback == null ? "" : fallback;
        String language = preferences.effectiveLanguage();
        String selected = value.optString(language, "").trim();
        String arabic = value.optString("ar", "").trim();
        if (!selected.isEmpty() && TranslationCoverage.isValidTargetText(selected, arabic, language)) {
            return selected;
        }
        String safeFallback = fallback == null ? "" : fallback.trim();
        if (!safeFallback.isEmpty()
                && TranslationCoverage.isValidTargetText(safeFallback, arabic, language)) {
            return safeFallback;
        }
        return "";
    }

    public JSONObject serviceCoverage(String serviceId) {
        JSONObject coverage = today().optJSONObject("service_coverage");
        if (coverage == null) coverage = fallbackServiceCoverage;
        JSONArray services = coverage == null ? null : coverage.optJSONArray("services");
        if (services == null) return null;
        for (int i = 0; i < services.length(); i++) {
            JSONObject item = services.optJSONObject(i);
            if (item != null && serviceId.equals(item.optString("service_id"))) return item;
        }
        return null;
    }

    public JSONArray registeredSources() {
        JSONArray sources = sourceRegistry().optJSONArray("sources");
        return sources == null ? new JSONArray() : sources;
    }

    public JSONObject sourceById(String sourceId) {
        if (sourceId == null || sourceId.trim().isEmpty()) return null;
        JSONArray sources = registeredSources();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject source = sources.optJSONObject(i);
            if (source != null && sourceId.equals(source.optString("id"))) return source;
        }
        return null;
    }

    public String sourceName(String sourceId) {
        JSONObject source = sourceById(sourceId);
        return source == null ? sourceId : localized(source.optJSONObject("name"), sourceId);
    }

    public String sourceUrl(String sourceId) {
        JSONObject source = sourceById(sourceId);
        return source == null ? "" : source.optString("url", "").trim();
    }


    public String dataDate() {
        JSONObject value = today();
        String date = value.optString("date_iso", "");
        return date.isEmpty() ? value.optString("date", "") : date;
    }

    public boolean isTodayCurrent() { return currentAmmanDate().equals(dataDate()); }

    public boolean hasDisplayableData() {
        JSONObject value = today();
        if (value == null || value.length() == 0) return false;
        if (!DataContract.supportsSchema(value.optInt("schema_version", 0))) return false;
        if (dataDate().trim().isEmpty()) return false;
        JSONObject dateLabel = value.optJSONObject("date_label");
        JSONObject fast = value.optJSONObject("fast");
        if (!hasLocalizedText(dateLabel)) return false;
        if (!hasLocalizedText(fast)) {
            JSONObject fasting = value.optJSONObject("fasting");
            if (fasting == null || !hasLocalizedText(fasting.optJSONObject("title"))) return false;
        }
        return true;
    }

    public boolean hasUsableCurrentData() {
        JSONObject value = today();
        return hasDisplayableData() && validate(value, currentAmmanDate(), true) == null;
    }

    /** Reload the best signed snapshot after the user changes the active language lane. */
    public synchronized void reloadForSelectedLanguage() {
        clearLanguageAssetCache();
        if (languageScopedStore) {
            dataStore = new DailyDataStore(context, preferences.effectiveLanguage());
        }
        loadedStoredSource = "";
        loadedStoredHash = "";
        loadError = "";
        activatePackage(loadBestToday());
        // The local package contains all three language lanes, so a language
        // switch can reuse it immediately without a synchronous rebuild.
        activateCachedLocalPackageIfAvailable();
    }

    public java.util.List<String> availableCachedDates() {
        return dataStore.availableDates();
    }

    public String local(int resourceId) {
        return LocalizedResources.get(context, preferences.effectiveLanguage(), resourceId);
    }

    public String localFormat(int resourceId, Object... arguments) {
        return LocalizedResources.format(context, preferences.effectiveLanguage(), resourceId, arguments);
    }

    public LocalizedValue localizedValue(JSONObject object, String fallback) {
        String language = preferences.effectiveLanguage();
        if (object == null) return new LocalizedValue(fallback, false);

        String arabic = DisplayTextSanitizer.sanitize(object.optString("ar", "").trim());
        String requested = DisplayTextSanitizer.sanitize(object.optString(language, "").trim());
        if ("ar".equals(language)) {
            if (TranslationCoverage.isValidTargetText(requested, arabic, language)) {
                return new LocalizedValue(requested, false);
            }
            String safeFallback = DisplayTextSanitizer.sanitize(
                    fallback == null ? "" : fallback.trim()
            );
            if (TranslationCoverage.isValidTargetText(safeFallback, arabic, language)) {
                return new LocalizedValue(safeFallback, false);
            }
            return new LocalizedValue(unavailableTranslationText(language), true);
        }

        if (TranslationCoverage.isValidTargetText(requested, arabic, language)) {
            return new LocalizedValue(requested, false);
        }

        String safeFallback = DisplayTextSanitizer.sanitize(fallback == null ? "" : fallback.trim());
        if (!safeFallback.isEmpty() && TranslationCoverage.isValidTargetText(safeFallback, arabic, language)) {
            return new LocalizedValue(safeFallback, false);
        }

        return new LocalizedValue(unavailableTranslationText(language), true);
    }

    public String unavailableTranslationText() {
        return unavailableTranslationText(preferences.effectiveLanguage());
    }

    private String unavailableTranslationText(String language) {
        if ("el".equals(language)) {
            return "Τὸ ἐπίσημο πρωτότυπο ἑλληνικὸ κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ τμήμα.";
        }
        if ("en".equals(language)) {
            return "The official native English text is not available for this section.";
        }
        return "النص العربي الأصلي المعتمد غير متوفر لهذا المقطع.";
    }

    public String localized(JSONObject object, String fallback) { return localizedValue(object, fallback).text; }

    public synchronized JSONObject searchIndex() {
        ensureLanguageAssets(preferences.effectiveLanguage(), true);
        return activeLanguageSearchIndex != null ? activeLanguageSearchIndex : new JSONObject();
    }

    public JSONArray searchDocuments() {
        JSONObject index = searchIndex();
        return index == null ? null : index.optJSONArray("documents");
    }

    public JSONArray currentReadings() {
        if (!isTodayCurrent()) return new JSONArray();
        JSONArray readings = today().optJSONArray("readings");
        return readings == null ? new JSONArray() : readings;
    }

    public JSONObject findService(String id) {
        String requestedId = id == null ? "" : id.trim();
        boolean libraryOnly = requestedId.startsWith("library::");
        if (libraryOnly) requestedId = requestedId.substring("library::".length()).trim();
        String date = "";
        String serviceId = requestedId;
        int separator = requestedId.indexOf("::");
        if (separator == 10 && requestedId.substring(0, 10).matches("\\d{4}-\\d{2}-\\d{2}")) {
            date = requestedId.substring(0, 10);
            serviceId = requestedId.substring(separator + 2);
        }

        JSONObject dynamic = !libraryOnly && isTodayCurrent()
                ? findServiceInArray(today().optJSONArray("services"), serviceId)
                : null;
        JSONObject selected = dynamic;
        if (!libraryOnly && !date.isEmpty()) {
            JSONObject day = rollingWeekByDate.get(date);
            selected = day == null ? null : findServiceInArray(day.optJSONArray("services"), serviceId);
        }

        if (selected == null) selected = findServiceInArray(library().optJSONArray("services"), serviceId);
        if (selected == null) {
            JSONObject index = searchIndex();
            selected = readerServiceFromSearchIndex(index, serviceId);
        }
        if (!isUserDisplayableService(selected)) return null;
        selected = composeBuiltInChurchService(selected);
        JSONObject resolved = resolveService(selected);
        return isFollowAlongLiturgy(resolved) ? composeFollowAlongLiturgy(resolved) : resolved;
    }

    /** Rebuild scripture reader services on demand from the search document.
     *
     * Search documents already contain the exact display text, hash, reference and
     * source metadata. Keeping a second serialized copy of every scripture passage
     * in reader_services added several megabytes to each language asset. Rebuilding
     * the lightweight reader object here preserves the exact native text while
     * keeping the APK/runtime asset budget bounded.
     */
    private JSONObject readerServiceFromSearchIndex(JSONObject index, String serviceId) {
        if (index == null || serviceId == null || serviceId.isEmpty()) return null;
        JSONArray documents = index.optJSONArray("documents");
        if (documents == null) return null;
        String language = index.optString("language", preferences.effectiveLanguage());
        for (int i = 0; i < documents.length(); i++) {
            JSONObject document = documents.optJSONObject(i);
            if (document == null || !"scripture".equals(document.optString("type", ""))) continue;
            if (!serviceId.equals(document.optString("target_id", ""))) continue;
            return scriptureReaderService(document, language);
        }
        return null;
    }

    private void collectReaderServicesFromSearchIndex(JSONObject index, Map<String, JSONObject> output) {
        if (index == null || output == null) return;
        JSONArray documents = index.optJSONArray("documents");
        if (documents == null) return;
        String language = index.optString("language", preferences.effectiveLanguage());
        for (int i = 0; i < documents.length(); i++) {
            JSONObject document = documents.optJSONObject(i);
            if (document == null || !"scripture".equals(document.optString("type", ""))) continue;
            JSONObject service = scriptureReaderService(document, language);
            if (isRenderableService(service) && isUserDisplayableService(service)) {
                output.putIfAbsent(service.optString("id", "scripture-" + i), resolveService(service));
            }
        }
    }

    private static JSONObject scriptureReaderService(JSONObject document, String language) {
        if (document == null) return null;
        String lang = "ar".equals(language) || "el".equals(language) ? language : "en";
        String id = document.optString("target_id", "").trim();
        String title = document.optString("title", "");
        String reference = document.optString("reference", "");
        String displayText = document.optString("display_text", "");
        if (id.isEmpty() || displayText.isEmpty()) return null;
        String fallbackSummary = "ar".equals(lang) ? "نص كتابي" : ("el".equals(lang) ? "Γραφή" : "Scripture");
        JSONObject localizedTitle = localizedOnly(lang, title);
        JSONObject localizedSummary = localizedOnly(lang, reference.isEmpty() ? fallbackSummary : reference);
        JSONObject localizedText = localizedOnly(lang, displayText);
        JSONObject source = document.optJSONObject("source");
        try {
            JSONObject service = new JSONObject();
            service.put("id", id);
            service.put("category", "scripture");
            service.put("icon", "📖");
            service.put("title", localizedTitle);
            service.put("summary", localizedSummary);
            service.put("segments", new JSONArray().put(new JSONObject()
                    .put("speaker", localizedTitle)
                    .put("text", localizedText)));
            service.put("content_mode", "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY");
            service.put("source_language", lang);
            service.put("native_source", new JSONObject()
                    .put("source_id", source == null ? "" : source.optString("source_id", ""))
                    .put("url", source == null ? "" : source.optString("url", ""))
                    .put("content_sha256", document.optString("display_sha256", ""))
                    .put("machine_translation_used", false));
            service.put("search_only", false);
            return service;
        } catch (Exception error) {
            return null;
        }
    }

    private static JSONObject localizedOnly(String language, String value) {
        JSONObject localized = new JSONObject();
        putQuietly(localized, "ar", "ar".equals(language) ? value : "");
        putQuietly(localized, "en", "en".equals(language) ? value : "");
        putQuietly(localized, "el", "el".equals(language) ? value : "");
        return localized;
    }

    /** Reuse already-audited native services instead of duplicating or translating text. */
    private JSONObject composeBuiltInChurchService(JSONObject service) {
        if (service == null || !"church_service".equals(service.optString("category", ""))) return service;
        String id = service.optString("id", "");
        try {
            if ("church_eucharist".equals(id)) {
                JSONObject liturgy = findServiceInArray(library().optJSONArray("services"), "divine_liturgy");
                if (liturgy == null) return service;
                JSONObject result = new JSONObject(liturgy.toString());
                // Preserve the Church Service card identity while using the complete native Liturgy text.
                result.put("id", id);
                result.put("category", "church_service");
                result.put("icon", service.optString("icon", "☦"));
                result.put("title", deepCopyJson(service.optJSONObject("title")));
                result.put("summary", deepCopyJson(service.optJSONObject("summary")));
                result.put("content_mode", "FULL_NATIVE_SERVICE_COMPOSED_FROM_AUDITED_LOCAL_ASSETS");
                result.put("publication_status", "FULL_NATIVE_RITE_TEXT_BUNDLED_OFFLINE");
                result.put("full_service", true);
                result.put("composed_from", "divine_liturgy");
                return result;
            }
            if ("church_hours".equals(id)) {
                JSONArray merged = new JSONArray();
                String[] hourIds = {"first_hour", "third_hour", "sixth_hour", "ninth_hour"};
                for (String hourId : hourIds) {
                    JSONObject hour = findServiceInArray(library().optJSONArray("services"), hourId);
                    if (hour == null) return service;
                    appendSegments(merged, hour.optJSONArray("segments"));
                }
                JSONObject result = new JSONObject(service.toString());
                result.put("segments", merged);
                result.put("content_mode", "FULL_NATIVE_SERVICE_COMPOSED_FROM_AUDITED_LOCAL_ASSETS");
                result.put("publication_status", "FULL_NATIVE_RITE_TEXT_BUNDLED_OFFLINE");
                result.put("full_service", true);
                result.put("composed_from", "first_third_sixth_ninth_hours");
                return result;
            }
        } catch (Exception error) {
            Log.w(TAG, "Could not compose built-in Church Service " + id, error);
        }
        return service;
    }

    public ArrayList<JSONObject> servicesByCategory(String category) {
        LinkedHashMap<String, JSONObject> unique = new LinkedHashMap<>();
        if (isTodayCurrent()) collectByCategory(today().optJSONArray("services"), category, unique);
        collectByCategory(library().optJSONArray("services"), category, unique);
        return new ArrayList<>(unique.values());
    }

    public ArrayList<JSONObject> allServices() {
        LinkedHashMap<String, JSONObject> unique = new LinkedHashMap<>();
        if (isTodayCurrent()) collectAll(today().optJSONArray("services"), unique);
        collectAll(library().optJSONArray("services"), unique);
        JSONObject index = searchIndex();
        if (index != null) collectReaderServicesFromSearchIndex(index, unique);
        return new ArrayList<>(unique.values());
    }

    /** Coverage of the requested native pack, independent of the language currently open in the UI. */
    public TranslationCoverage.Result nativeContentCoverage(String language) {
        return TranslationCoverage.measure(libraryForLanguage(language), language);
    }

    public int religiousCompleteServiceCount(String language) {
        JSONObject languages = religiousCompleteness == null
                ? null : religiousCompleteness.optJSONObject("languages");
        JSONObject statuses = languages == null ? null : languages.optJSONObject(language);
        if (statuses == null) return 0;
        int complete = 0;
        Iterator<String> keys = statuses.keys();
        while (keys.hasNext()) {
            if ("complete_exact_native_edition".equals(statuses.optString(keys.next()))) complete++;
        }
        return complete;
    }

    public int religiousRequiredServiceCount() {
        JSONArray required = religiousCompleteness == null
                ? null : religiousCompleteness.optJSONArray("required_services");
        return required == null ? 0 : required.length();
    }

    /** Backwards-compatible name retained for older screens and tests. */
    public TranslationCoverage.Result translationCoverage(String language) {
        return nativeContentCoverage(language);
    }

    public void refreshAsync(RefreshCallback callback) { refreshAsync(false, callback); }

    public void refreshAsync(boolean forceFullDownload, RefreshCallback callback) {
        if (callback == null) return;
        if (!beginRefresh()) {
            mainHandler.post(() -> callback.onComplete(RefreshResult.NOT_MODIFIED, "refresh_in_progress"));
            return;
        }
        executor.execute(() -> {
            RefreshOutcome outcome = executeStartedRefresh(forceFullDownload);
            mainHandler.post(() -> callback.onComplete(outcome.result, outcome.message));
        });
    }

    public RefreshOutcome refreshBlocking() { return refreshBlocking(false); }

    public RefreshOutcome refreshBlocking(boolean forceFullDownload) {
        if (!beginRefresh()) return new RefreshOutcome(RefreshResult.NOT_MODIFIED, "refresh_in_progress");
        return executeStartedRefresh(forceFullDownload);
    }

    private boolean beginRefresh() {
        synchronized (refreshGuard) {
            if (refreshInProgress) return false;
            refreshInProgress = true;
            refreshState = RefreshState.REFRESHING;
            refreshMessage = "refreshing";
            return true;
        }
    }

    private RefreshOutcome executeStartedRefresh(boolean forceFullDownload) {
        try {
            RefreshOutcome outcome;
            try {
                outcome = performRefresh(forceFullDownload || !hasUsableCurrentData());
            } catch (Exception error) {
                Log.e(TAG, "Unexpected daily-data refresh failure", error);
                outcome = new RefreshOutcome(RefreshResult.FAILED, classifyError(error));
            }
            if (outcome.result == RefreshResult.UPDATED) refreshState = RefreshState.UPDATED;
            else if (outcome.result == RefreshResult.NOT_MODIFIED) refreshState = RefreshState.CURRENT;
            else refreshState = RefreshState.FAILED;
            refreshMessage = outcome.message;
            preferences.recordRefreshOutcome(outcome.result != RefreshResult.FAILED, outcome.message, System.currentTimeMillis());
            return outcome;
        } finally {
            synchronized (refreshGuard) { refreshInProgress = false; }
        }
    }

    /**
     * The daily update is local-first and succeeds without a network connection.
     * Remote signed-data code is retained below only as an optional compatibility
     * path for a future owner-controlled correction channel; automatic daily work
     * never depends on it.
     */
    private RefreshOutcome performRefresh(boolean forceRebuild) {
        try {
            String date = currentAmmanDate();
            JSONObject local = localDailyContentEngine.buildCurrentWindow(LocalDate.parse(date));
            byte[] encoded = local.toString().getBytes(StandardCharsets.UTF_8);
            String localHash = sha256(encoded);
            boolean changed = forceRebuild
                    || !date.equals(dataDate())
                    || !localHash.equalsIgnoreCase(contentHash)
                    || !"local_offline_engine".equals(trustSource);
            synchronized (this) { activatePackage(local); }
            trustSource = "local_offline_engine";
            contentHash = localHash;
            loadError = "";
            try {
                localDailyCacheStore.save(encoded);
            } catch (Exception cacheError) {
                // The in-memory package is already valid. A cache write failure
                // must never make Daily Update fail or block the UI.
                Log.w(TAG, "Local daily cache could not be saved", cacheError);
            }
            return new RefreshOutcome(
                    changed ? RefreshResult.UPDATED : RefreshResult.NOT_MODIFIED,
                    changed ? "updated_local_offline" : "local_offline_current"
            );
        } catch (Exception error) {
            Log.e(TAG, "Local daily package could not be built", error);
            return new RefreshOutcome(
                    RefreshResult.FAILED,
                    "local_calendar_unavailable:" + safeMessage(error, "unknown")
            );
        }
    }

    private void activateCachedLocalPackageIfAvailable() {
        try {
            byte[] cachedBytes = localDailyCacheStore.read();
            if (cachedBytes == null || cachedBytes.length == 0) return;
            JSONObject cached = new JSONObject(new String(cachedBytes, StandardCharsets.UTF_8));
            String error = validate(cached, currentAmmanDate(), true);
            if (error != null) {
                localDailyCacheStore.clear();
                return;
            }
            synchronized (this) { activatePackage(cached); }
            trustSource = "local_offline_engine";
            contentHash = sha256(cachedBytes);
            loadError = "";
            refreshState = RefreshState.CURRENT;
            refreshMessage = "local_offline_current";
        } catch (Exception cacheError) {
            localDailyCacheStore.clear();
            Log.w(TAG, "Cached local daily package was rejected", cacheError);
        }
    }

    @SuppressWarnings("unused")
    private RefreshOutcome performRemoteRefresh(boolean forceFullDownload) {
        if (!NetworkAvailability.hasConnectedNetwork(context)) {
            return new RefreshOutcome(RefreshResult.FAILED, "network_offline");
        }

        String configuredTodayUrl = context.getString(R.string.data_source_url).trim();
        String configuredTodaySignatureUrl = context.getString(R.string.data_signature_url).trim();
        String configuredTodayMirrorUrl = context.getString(R.string.data_source_mirror_url).trim();
        String configuredTodayMirrorSignatureUrl = context.getString(R.string.data_signature_mirror_url).trim();
        String configuredManifestUrl = context.getString(R.string.update_manifest_url).trim();
        String configuredManifestSignatureUrl = context.getString(R.string.update_manifest_signature_url).trim();
        String configuredManifestMirrorUrl = context.getString(R.string.update_manifest_mirror_url).trim();
        String configuredManifestMirrorSignatureUrl = context.getString(R.string.update_manifest_signature_mirror_url).trim();
        if (configuredTodayUrl.isEmpty() && configuredTodayMirrorUrl.isEmpty()) {
            return new RefreshOutcome(RefreshResult.FAILED, "data_url_missing");
        }

        UpdateManifest.Selection manifestSelection = null;
        Exception manifestError = null;
        Set<String> attemptedManifestUrls = new LinkedHashSet<>();
        String[][] manifestEndpoints = {
                {configuredManifestUrl, configuredManifestSignatureUrl},
                {configuredManifestMirrorUrl, configuredManifestMirrorSignatureUrl}
        };
        for (String[] endpoint : manifestEndpoints) {
            String manifestUrl = endpoint[0];
            String signatureUrl = endpoint[1];
            if (manifestUrl.isEmpty() || signatureUrl.isEmpty()
                    || !attemptedManifestUrls.add(manifestUrl)) continue;
            try {
                manifestSelection = downloadManifestSelection(manifestUrl, signatureUrl);
                break;
            } catch (Exception error) {
                manifestError = error;
                Log.w(TAG, "Signed update manifest endpoint was unavailable; trying fallback", error);
                String message = error.getMessage() == null ? "" : error.getMessage();
                if (message.startsWith("app_update_required")
                        || message.startsWith("manifest_revision_rollback")) {
                    return new RefreshOutcome(RefreshResult.FAILED, message);
                }
            }
        }

        if (manifestSelection == null) {
            if (ManifestSecurityPolicy.mustFailClosed(manifestError)) {
                return new RefreshOutcome(RefreshResult.FAILED, classifyError(manifestError));
            }
            String expectedDate = currentAmmanDate();
            if (preferences.acceptedManifestRevisionForDate(expectedDate) > 0L) {
                return new RefreshOutcome(
                        RefreshResult.FAILED,
                        "manifest_unavailable_after_acceptance"
                );
            }
        }

        if (manifestSelection != null) {
            String expectedDate = currentAmmanDate();
            long acceptedRevision = preferences.acceptedManifestRevisionForDate(expectedDate);
            if (manifestSelection.revision < acceptedRevision) {
                return new RefreshOutcome(
                        RefreshResult.FAILED,
                        "manifest_revision_rollback:" + manifestSelection.revision + ":" + acceptedRevision
                );
            }
            if (hasUsableCurrentData()
                    && manifestSelection.sha256.equalsIgnoreCase(contentHash)) {
                preferences.saveAcceptedManifest(expectedDate, manifestSelection.revision);
                return new RefreshOutcome(RefreshResult.NOT_MODIFIED, "manifest_not_modified");
            }

            Exception lastManifestPayloadError = null;
            for (int attempt = 0; attempt < MAX_DOWNLOAD_ATTEMPTS; attempt++) {
                try {
                    return downloadAndValidate(
                            manifestSelection.dataUrl,
                            manifestSelection.signatureUrl,
                            forceFullDownload || attempt > 0,
                            attempt,
                            manifestSelection.sha256,
                            manifestSelection.sizeBytes,
                            manifestSelection.revision
                    );
                } catch (Exception error) {
                    lastManifestPayloadError = error;
                    Log.w(TAG, "Manifest-selected daily payload attempt " + (attempt + 1) + " failed", error);
                    if (attempt + 1 < MAX_DOWNLOAD_ATTEMPTS) {
                        try { Thread.sleep(350L); }
                        catch (InterruptedException interrupted) {
                            Thread.currentThread().interrupt();
                            return new RefreshOutcome(RefreshResult.FAILED, "network_interrupted");
                        }
                    }
                }
            }
            return new RefreshOutcome(RefreshResult.FAILED, classifyError(lastManifestPayloadError));
        }

        Exception lastError = manifestError;
        int endpointIndex = 0;
        Set<String> attemptedJsonUrls = new LinkedHashSet<>();
        String[][] dailyEndpoints = {
                {configuredTodayUrl, configuredTodaySignatureUrl},
                {configuredTodayMirrorUrl, configuredTodayMirrorSignatureUrl}
        };
        for (String[] endpoint : dailyEndpoints) {
            String todayUrl = endpoint[0];
            String todaySignatureUrl = endpoint[1];
            if (todayUrl.isEmpty()) continue;
            for (String jsonUrl : DailyDataEndpointPolicy.jsonCandidates(
                    todayUrl,
                    currentAmmanDate(),
                    preferences.effectiveLanguage()
            )) {
                if (!attemptedJsonUrls.add(jsonUrl)) continue;
                String signatureUrl = DailyDataEndpointPolicy.signatureUrl(
                        todayUrl,
                        todaySignatureUrl,
                        jsonUrl
                );
                for (int attempt = 0; attempt < MAX_DOWNLOAD_ATTEMPTS; attempt++) {
                    boolean bypassCache = forceFullDownload || endpointIndex > 0 || attempt > 0;
                    try {
                        return downloadAndValidate(
                                jsonUrl, signatureUrl, bypassCache, attempt, "", 0, 0L
                        );
                    } catch (Exception error) {
                        lastError = error;
                        Log.w(
                                TAG,
                                "Daily data refresh endpoint " + (endpointIndex + 1)
                                        + " attempt " + (attempt + 1) + " failed",
                                error
                        );
                        if (attempt + 1 < MAX_DOWNLOAD_ATTEMPTS) {
                            try { Thread.sleep(350L); }
                            catch (InterruptedException interrupted) {
                                Thread.currentThread().interrupt();
                                return new RefreshOutcome(RefreshResult.FAILED, "network_interrupted");
                            }
                        }
                    }
                }
                endpointIndex++;
            }
        }
        return new RefreshOutcome(RefreshResult.FAILED, classifyError(lastError));
    }


    private UpdateManifest.Selection downloadManifestSelection(
            String manifestUrl,
            String manifestSignatureUrl
    ) throws Exception {
        String token = "m=" + System.currentTimeMillis();
        HttpURLConnection connection = null;
        try {
            connection = open(appendQuery(manifestUrl, token), MAX_MANIFEST_BYTES, true);
            int code = connection.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK) {
                throw new IllegalStateException("manifest_http_" + code);
            }
            validateContentType(connection);
            byte[] manifestBytes = readLimited(connection.getInputStream(), MAX_MANIFEST_BYTES);
            byte[] signatureBytes = downloadSignature(manifestSignatureUrl, true, token);
            signatureVerifier.verify(manifestBytes, signatureBytes);
            UpdateManifest.Selection selection = UpdateManifest.parse(
                    manifestBytes,
                    manifestUrl,
                    currentAmmanDate(),
                    preferences.effectiveLanguage()
            );
            if (selection.minimumAppVersionCode > BuildConfig.VERSION_CODE) {
                throw new IllegalStateException(
                        "app_update_required:" + selection.minimumAppVersionCode
                );
            }
            long acceptedRevision = preferences.acceptedManifestRevisionForDate(currentAmmanDate());
            if (selection.revision < acceptedRevision) {
                throw new IllegalStateException(
                        "manifest_revision_rollback:" + selection.revision + ":" + acceptedRevision
                );
            }
            return selection;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private RefreshOutcome downloadAndValidate(
            String jsonUrl,
            String signatureUrl,
            boolean bypassCache,
            int attempt,
            String expectedSha256,
            int expectedSizeBytes,
            long manifestRevision
    ) throws Exception {
        HttpURLConnection connection = null;
        try {
            String token = "r=" + System.currentTimeMillis() + "-" + attempt;
            String requestedUrl = bypassCache ? appendQuery(jsonUrl, token) : jsonUrl;
            connection = open(requestedUrl, MAX_JSON_BYTES, bypassCache);
            String etag = preferences.cachedEtag(jsonUrl);
            boolean remoteCacheLoaded = "signed_remote".equals(trustSource) || "signed_cache".equals(trustSource);
            if (!bypassCache && remoteCacheLoaded && hasUsableCurrentData() && !etag.isEmpty()) {
                connection.setRequestProperty("If-None-Match", etag);
            }

            int code = connection.getResponseCode();
            if (code == HttpURLConnection.HTTP_NOT_MODIFIED) {
                if (hasUsableCurrentData()) {
                    if (manifestRevision > 0L) {
                        preferences.saveAcceptedManifest(currentAmmanDate(), manifestRevision);
                    }
                    return new RefreshOutcome(RefreshResult.NOT_MODIFIED, "not_modified");
                }
                throw new IllegalStateException("not_modified_without_usable_cache");
            }
            if (code != HttpURLConnection.HTTP_OK) throw new IllegalStateException("http_" + code);
            validateContentType(connection);
            byte[] jsonBytes = readLimited(connection.getInputStream(), MAX_JSON_BYTES);
            if (expectedSizeBytes > 0 && jsonBytes.length != expectedSizeBytes) {
                throw new IllegalStateException("manifest_payload_size_mismatch");
            }
            String downloadedHash = sha256(jsonBytes);
            if (expectedSha256 != null && !expectedSha256.isEmpty()
                    && !expectedSha256.equalsIgnoreCase(downloadedHash)) {
                throw new IllegalStateException("manifest_payload_hash_mismatch");
            }
            if (signatureUrl == null || signatureUrl.trim().isEmpty()) {
                throw new IllegalStateException("signature_url_missing");
            }
            byte[] signatureBytes = downloadSignature(signatureUrl, bypassCache, token);
            signatureVerifier.verify(jsonBytes, signatureBytes);

            JSONObject parsed = new JSONObject(new String(jsonBytes, StandardCharsets.UTF_8));
            String currentDate = currentAmmanDate();
            boolean rollingPackage = hasRollingWindow(parsed);
            String validationDate = rollingPackage
                    ? parsed.optString("date_iso", "").trim()
                    : currentDate;
            String validationError = validate(parsed, validationDate, true);
            if (validationError != null && !isRecoverableReadingValidation(validationError)) {
                throw new IllegalStateException(validationError);
            }
            if (validationError != null) {
                Log.w(TAG, "Signed package contains a recoverable reading-evidence issue: " + validationError);
            }
            String rollingError = validateRollingWeekPackage(parsed);
            if (rollingError != null) throw new IllegalStateException(rollingError);
            if (rollingPackage && !rollingPackageContainsDate(parsed, currentDate)) {
                throw new IllegalStateException(
                        "date_not_ready:" + parsed.optString("date_iso", "") + ":" + currentDate
                );
            }
            String translationError = VerifiedContentSanitizer.firstUnsafeTranslationError(parsed);
            if (!translationError.isEmpty()) {
                Log.w(TAG, "Signed package contains a reading that will be suppressed: " + translationError);
            }
            // The package signature and manifest SHA authenticate the bytes. Suppress
            // only the unsafe reading in memory instead of rejecting all eight days.
            VerifiedContentSanitizer.sanitize(parsed);
            VerifiedContentSanitizer.sanitizeFutureDays(parsed);
            String regression = DailySnapshotRegressionGuard.firstRegression(
                    today,
                    parsed,
                    preferences.effectiveLanguage()
            );
            if (!regression.isEmpty()) throw new IllegalStateException(regression);

            dataStore.saveVerified(jsonBytes, signatureBytes);
            String newEtag = connection.getHeaderField("ETag");
            long now = System.currentTimeMillis();
            preferences.saveRemoteMetadata(newEtag, jsonUrl, now);
            if (manifestRevision > 0L) {
                preferences.saveAcceptedManifest(currentAmmanDate(), manifestRevision);
            }
            synchronized (this) { activatePackage(parsed); }
            trustSource = "signed_remote";
            contentHash = downloadedHash;
            loadError = "";
            return new RefreshOutcome(
                    RefreshResult.UPDATED,
                    manifestRevision > 0L ? "updated_via_manifest" : "updated_signed"
            );
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private byte[] downloadSignature(String signatureUrl, boolean bypassCache, String token) throws Exception {
        HttpURLConnection signatureConnection = null;
        try {
            String requestedUrl = bypassCache ? appendQuery(signatureUrl, token) : signatureUrl;
            signatureConnection = open(requestedUrl, MAX_SIGNATURE_BYTES, bypassCache);
            int code = signatureConnection.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK) throw new IllegalStateException("signature_http_" + code);
            return readLimited(signatureConnection.getInputStream(), MAX_SIGNATURE_BYTES);
        } finally {
            if (signatureConnection != null) signatureConnection.disconnect();
        }
    }

    public String validate(JSONObject data, String expectedDate, boolean requireExpectedDate) {
        return validate(data, expectedDate, requireExpectedDate, false);
    }

    private String validate(JSONObject data, String expectedDate, boolean requireExpectedDate, boolean allowFuture) {
        if (data == null || data.length() == 0) return "payload_empty";
        if (!DataContract.supportsSchema(data.optInt("schema_version", 0))) return "schema_unsupported";
        String date = data.optString("date_iso", data.optString("date", ""));
        if (date.trim().isEmpty()) return "date_missing";
        try {
            LocalDate parsedDate = LocalDate.parse(date);
            LocalDate ammanToday = LocalDate.parse(currentAmmanDate());
            if (!allowFuture && parsedDate.isAfter(ammanToday)) return "date_in_future:" + date;
        } catch (Exception error) {
            return "date_invalid:" + date;
        }
        if (requireExpectedDate && !expectedDate.equals(date)) return "date_not_ready:" + date;
        String payloadLanguage = data.optString("language", "").trim();
        if (!payloadLanguage.isEmpty()) {
            if (!preferences.effectiveLanguage().equals(payloadLanguage)) {
                return "language_lane_mismatch:" + payloadLanguage;
            }
            if (data.optInt("lane_schema_version", 0) < DataContract.MIN_LANGUAGE_LANE_SCHEMA_VERSION) return "language_lane_schema_unsupported";
            JSONArray laneServices = data.optJSONArray("services");
            if (laneServices == null || laneServices.length() == 0) return "language_lane_services_missing";
        }
        JSONArray services = data.optJSONArray("services");
        if (services == null || services.length() == 0) return "services_missing";
        String servicesError = validateServices(services);
        if (servicesError != null) return servicesError;

        // The server performs source-heavy validation. The phone verifies the
        // signature, date, schema and the structure of each available lane,
        // then displays every verified section that is present. A missing
        // language or optional service must never reject the entire day.
        if (!hasLocalizedText(data.optJSONObject("date_label"))) return "date_label_missing";
        if (data.optBoolean("machine_translation_used", true)) return "machine_translation_flag_invalid";
        if (data.optBoolean("automatic_diacritization_used", true)) return "automatic_diacritization_flag_invalid";
        JSONArray readings = data.optJSONArray("readings");
        if (readings == null) return "readings_missing";
        boolean anyEpistleOrGospel = false;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null) continue;
            String kind = reading.optString("kind", "");
            if ("epistle".equals(kind) || "gospel".equals(kind)) anyEpistleOrGospel = true;
            JSONObject body = reading.optJSONObject("body");
            JSONObject verification = reading.optJSONObject("native_source_verification");
            if (body == null || verification == null) continue;
            for (String language : new String[]{"ar", "en", "el"}) {
                String text = body.optString(language, "").trim();
                if (text.isEmpty()) continue;
                JSONObject evidence = verification.optJSONObject(language);
                if (evidence == null) return kind + "_" + language + "_evidence_missing";
                if (evidence.optBoolean("ai_translation_used", true)) return kind + "_" + language + "_ai_flag_invalid";
                if (evidence.optBoolean("automatic_diacritization_used", true)) return kind + "_" + language + "_diacritization_flag_invalid";
                String status = evidence.optString("status", "");
                if (!"VERIFIED_EXACT_NATIVE_SOURCE".equals(status)
                        && !"IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS".equals(status)
                        && !"IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS".equals(status)) {
                    return kind + "_" + language + "_text_unverified";
                }
                if (!sha256(text.getBytes(StandardCharsets.UTF_8)).equalsIgnoreCase(evidence.optString("text_sha256", ""))) {
                    return kind + "_" + language + "_hash_invalid";
                }
            }
        }
        return anyEpistleOrGospel ? null : "scripture_reference_missing";
    }

    private static boolean isRecoverableReadingValidation(String error) {
        if (error == null || error.isEmpty()) return false;
        return error.endsWith("_evidence_missing")
                || error.endsWith("_ai_flag_invalid")
                || error.endsWith("_diacritization_flag_invalid")
                || error.endsWith("_text_unverified")
                || error.endsWith("_hash_invalid")
                || error.startsWith("unverified_scripture_native_text:");
    }

    static boolean hasRollingWindow(JSONObject packagePayload) {
        return packagePayload != null
                && packagePayload.optJSONObject("rolling_week") != null
                && packagePayload.optJSONArray("weekly_days") != null;
    }

    static boolean rollingPackageContainsDate(JSONObject packagePayload, String expectedDate) {
        if (!hasRollingWindow(packagePayload)) return false;
        String requested = expectedDate == null ? "" : expectedDate.trim();
        if (requested.isEmpty()) return false;
        if (requested.equals(packagePayload.optString("date_iso", "").trim())) return true;
        JSONArray future = packagePayload.optJSONArray("weekly_days");
        if (future == null) return false;
        for (int i = 0; i < future.length(); i++) {
            JSONObject day = future.optJSONObject(i);
            if (day != null && requested.equals(day.optString("date_iso", "").trim())) {
                return true;
            }
        }
        return false;
    }

    private String validateRollingWeekPackage(JSONObject packagePayload) {
        JSONObject metadata = packagePayload.optJSONObject("rolling_week");
        if (metadata == null) return null; // Backwards-compatible signed daily snapshot.
        if (!isSupportedRollingWindowMetadata(metadata)) return "rolling_week_schema_or_policy_unsupported";
        if (!"COMPLETE".equals(metadata.optString("status", ""))
                || !metadata.optBoolean("fail_closed", false)) return "rolling_week_incomplete";
        int dayCount = metadata.optInt("day_count", 0);
        String startValue = metadata.optString("start_date", "");
        String endValue = metadata.optString("end_date", "");
        if (!startValue.equals(packagePayload.optString("date_iso", ""))) return "rolling_week_start_mismatch";
        LocalDate start;
        try {
            start = LocalDate.parse(startValue);
            if (!start.plusDays(dayCount - 1L).toString().equals(endValue)) return "rolling_week_end_mismatch";
        } catch (Exception error) {
            return "rolling_week_date_invalid";
        }
        JSONArray future = packagePayload.optJSONArray("weekly_days");
        if (future == null || future.length() != dayCount - 1) return "rolling_week_members_missing";
        String anchorLiturgyError = validateAppointedLiturgy(packagePayload);
        if (anchorLiturgyError != null) {
            return "rolling_week_" + startValue + "_" + anchorLiturgyError;
        }
        for (int i = 0; i < dayCount - 1; i++) {
            JSONObject day = future.optJSONObject(i);
            if (day == null) return "rolling_week_member_invalid:" + i;
            String expected = start.plusDays(i + 1L).toString();
            String error = validate(day, expected, true, true);
            if (error != null && !isRecoverableReadingValidation(error)) {
                return "rolling_week_" + expected + "_" + error;
            }
            if (error != null) {
                Log.w(TAG, "Future day " + expected + " has a recoverable reading-evidence issue: " + error);
            }
            JSONObject publication = day.optJSONObject("publication");
            if (publication == null || !"FULL".equals(publication.optString("daily_availability", ""))) {
                return "rolling_week_" + expected + "_not_full";
            }
            String liturgyError = validateAppointedLiturgy(day);
            if (liturgyError != null) {
                return "rolling_week_" + expected + "_" + liturgyError;
            }
        }
        return null;
    }

    private static String validateAppointedLiturgy(JSONObject day) {
        JSONObject selection = day == null ? null : day.optJSONObject("liturgy_service_selection");
        if (selection == null) return "appointed_liturgy_selection_missing";
        String selectedType = selection.optString("service_type", "").trim();
        String serviceForm = selection.optString("service_form", "").trim();
        if (selectedType.isEmpty()) return "appointed_liturgy_type_missing";
        if (serviceForm.isEmpty()) return "appointed_liturgy_form_missing";
        if (selection.optJSONObject("reason") == null) return "appointed_liturgy_reason_missing";
        if (selection.optBoolean("wrong_liturgy_fallback_allowed", true)) {
            return "appointed_liturgy_fallback_enabled";
        }

        JSONObject service = findServiceInArray(day.optJSONArray("services"), "divine_liturgy");
        if (service == null) return "appointed_liturgy_service_missing";
        if (!selectedType.equals(service.optString("selected_liturgy_type", ""))) {
            return "appointed_liturgy_type_mismatch";
        }
        String publicationStatus = service.optString("publication_status", "");
        if ("no_divine_liturgy".equals(selectedType)) {
            return "NO_DIVINE_LITURGY_APPOINTED".equals(publicationStatus)
                    ? null : "no_liturgy_status_invalid";
        }
        if ("typikon_override_required".equals(selectedType)) {
            return "dated_typikon_override_required";
        }
        if (!selection.optBoolean("displayable", false)) {
            return "appointed_liturgy_complete_native_edition_missing";
        }
        if (!service.optBoolean("full_service_complete", false)) {
            return "appointed_liturgy_not_complete_from_beginning_to_end";
        }
        if (!publicationStatus.startsWith("DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END")) {
            return "appointed_liturgy_publication_status_invalid";
        }
        if (service.optString("extends_service_id", "").trim().isEmpty()) {
            return "appointed_liturgy_template_missing";
        }
        return null;
    }

    private synchronized void activatePackage(JSONObject candidate) {
        rollingWeekPackage = candidate == null ? new JSONObject() : candidate;
        rollingWeekByDate.clear();
        if (rollingWeekPackage.length() == 0) {
            today = new JSONObject();
            return;
        }
        String rootDate = rollingWeekPackage.optString("date_iso", "").trim();
        if (!rootDate.isEmpty()) rollingWeekByDate.put(rootDate, rollingWeekPackage);
        JSONArray future = rollingWeekPackage.optJSONArray("weekly_days");
        if (future != null) {
            for (int i = 0; i < future.length(); i++) {
                JSONObject day = future.optJSONObject(i);
                if (day == null) continue;
                String date = day.optString("date_iso", "").trim();
                if (!date.isEmpty()) rollingWeekByDate.put(date, day);
            }
        }
        JSONObject active = rollingWeekByDate.get(currentAmmanDate());
        today = active != null ? active : rollingWeekPackage;
    }

    public static boolean isRetryableRefreshMessage(String message) {
        String value = message == null ? "" : message;
        return value.startsWith("network_")
                || value.startsWith("server_")
                || value.startsWith("secure_connection_")
                || value.startsWith("http_")
                || value.startsWith("date_not_ready")
                || value.startsWith("signature_http_")
                || value.startsWith("manifest_unavailable_after_acceptance");
    }

    public String userFacingRefreshStatus() {
        if (isRefreshing()) return local(com.orthodoxprayers.privateapp.R.string.ui_updating_the_week_s_services_automatically_f680f00e);
        String code = refreshMessage == null || refreshMessage.isEmpty() ? preferences.lastRefreshMessage() : refreshMessage;
        if (code == null || code.isEmpty()) {
            if (hasUsableCurrentData()) return local(com.orthodoxprayers.privateapp.R.string.ui_today_and_the_coming_week_are_ready_1a099eed);
            return local(com.orthodoxprayers.privateapp.R.string.ui_waiting_for_the_weekly_service_update_0c0844a8);
        }
        if ("updated_local_offline".equals(code)) return local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_ready);
        if ("local_offline_current".equals(code)) return local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_current);
        if (code.startsWith("local_calendar_unavailable")) return local(com.orthodoxprayers.privateapp.R.string.ui_local_daily_update_unavailable);
        if ("updated".equals(code) || "updated_signed".equals(code) || "updated_via_manifest".equals(code)) return local(com.orthodoxprayers.privateapp.R.string.ui_the_eight_day_service_package_was_updated_and_ve_9ae074b7);
        if ("not_modified".equals(code) || "manifest_not_modified".equals(code)) return local(com.orthodoxprayers.privateapp.R.string.ui_the_weekly_services_are_already_current_2b76496f);
        if ("refresh_in_progress".equals(code) || "refreshing".equals(code)) return local(com.orthodoxprayers.privateapp.R.string.ui_an_update_is_already_in_progress_0afb7ec0);
        if (code.startsWith("app_update_required")) return local(com.orthodoxprayers.privateapp.R.string.ui_the_app_must_be_updated_to_read_today_s_new_data_bcfbcddc);
        if (code.startsWith("manifest_revision_rollback")) return local(com.orthodoxprayers.privateapp.R.string.ui_an_older_data_revision_was_rejected_for_update_s_5238c511);
        if (code.startsWith("manifest_unavailable_after_acceptance")
                || code.startsWith("manifest_expired")
                || code.startsWith("manifest_publication_time")
                || code.startsWith("manifest_validity_window")) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_the_secure_update_manifest_could_not_be_verified_d5b624be);
        }
        if (code.contains("invalid_json_size") || code.contains("stored_file_size_invalid") || code.contains("response_too_large") || code.contains("manifest_size_invalid")) {
            return local(com.orthodoxprayers.privateapp.R.string.ui_the_app_must_be_updated_to_read_today_s_new_data_bcfbcddc);
        }
        if (code.startsWith("date_not_ready") || code.startsWith("server_data_not_ready") || code.startsWith("server_manifest_not_ready")) return local(com.orthodoxprayers.privateapp.R.string.ui_today_s_update_is_still_being_published_the_last_d93b9203);
        if (code.startsWith("secure_connection_")) return local(com.orthodoxprayers.privateapp.R.string.ui_a_secure_connection_to_the_update_server_could_n_22125562);
        if (code.startsWith("server_") || code.startsWith("http_")) return local(com.orthodoxprayers.privateapp.R.string.ui_the_update_server_is_delayed_or_temporarily_unav_1cb313a4);
        if (code.startsWith("network_offline") || code.startsWith("network_unreachable")) return local(com.orthodoxprayers.privateapp.R.string.ui_the_phone_is_not_connected_to_a_network_the_last_55893d04);
        if (code.startsWith("network_dns_") || code.startsWith("network_io_")) return local(com.orthodoxprayers.privateapp.R.string.ui_internet_is_connected_but_the_update_host_could__21495ffe);
        if (code.startsWith("network_")) return local(com.orthodoxprayers.privateapp.R.string.ui_the_update_server_could_not_be_contacted_tempora_dc3cce39);
        if (code.contains("signature")) return local(com.orthodoxprayers.privateapp.R.string.ui_the_update_signature_failed_and_was_rejected_the_7105a062);
        if (code.startsWith("invalid_")) return local(com.orthodoxprayers.privateapp.R.string.ui_incomplete_or_invalid_data_was_received_and_igno_e2b95466);
        if (preferences.lastRefreshSucceeded()) return local(com.orthodoxprayers.privateapp.R.string.ui_the_last_update_check_completed_successfully_bb37cd88);
        return local(com.orthodoxprayers.privateapp.R.string.ui_update_failed_the_last_valid_saved_copy_is_shown_ed557cb3);
    }

    private JSONObject loadBestToday() {
        JSONObject cached = loadCachedCandidate();
        JSONObject embedded = loadAssetCandidate();
        JSONObject best = newer(cached, embedded);
        if (best == cached && cached != null) {
            trustSource = loadedStoredSource;
            contentHash = loadedStoredHash;
            return cached;
        }
        if (best == embedded && embedded != null) {
            trustSource = "signed_embedded";
            contentHash = loadedEmbeddedHash;
            return embedded;
        }
        if (loadError.isEmpty()) loadError = "no_valid_daily_data";
        return new JSONObject();
    }

    private JSONObject loadCachedCandidate() {
        JSONObject current = loadStoredCandidate(false);
        if (current != null) return current;
        return loadStoredCandidate(true);
    }

    private JSONObject loadStoredCandidate(boolean backup) {
        try {
            DailyDataStore.StoredPayload stored = backup ? dataStore.readBackup() : dataStore.readCurrent();
            if (stored == null) return null;
            JSONObject candidate = parseTrustedCandidate(stored.json, stored.signature, false);
            loadedStoredSource = backup ? "signed_backup" : "signed_cache";
            loadedStoredHash = sha256(stored.json);
            return candidate;
        } catch (Exception error) {
            if (!backup) dataStore.deleteCurrent();
            loadError = (backup ? "backup_" : "cached_") + safeMessage(error, "invalid");
            Log.w(TAG, "Stored signed data rejected", error);
            return null;
        }
    }

    private JSONObject loadAssetCandidate() {
        try {
            byte[] payload = readAssetBytes("data/today.json", MAX_JSON_BYTES);
            byte[] signature = readAssetBytes("data/today.json.sig", MAX_SIGNATURE_BYTES);
            JSONObject embedded = parseTrustedCandidate(payload, signature, false);
            loadedEmbeddedHash = sha256(payload);
            return embedded;
        } catch (Exception error) {
            loadError = safeMessage(error, "embedded_data_invalid");
            Log.e(TAG, "Embedded signed data could not be loaded", error);
            return null;
        }
    }

    private JSONObject parseTrustedCandidate(byte[] payload, byte[] signature, boolean requireToday) throws Exception {
        signatureVerifier.verify(payload, signature);
        JSONObject candidate = new JSONObject(new String(payload, StandardCharsets.UTF_8));
        String validationError = validate(candidate, currentAmmanDate(), requireToday);
        if (validationError != null && !isRecoverableReadingValidation(validationError)) {
            throw new IllegalStateException(validationError);
        }
        String rollingError = validateRollingWeekPackage(candidate);
        if (rollingError != null) throw new IllegalStateException(rollingError);
        VerifiedContentSanitizer.sanitize(candidate);
        VerifiedContentSanitizer.sanitizeFutureDays(candidate);
        return candidate;
    }

    private JSONObject loadJsonAsset(String path) {
        try {
            return new JSONObject(new String(readAssetBytes(path, 10_000_000), StandardCharsets.UTF_8));
        } catch (Exception error) {
            Log.e(TAG, "Asset load failed: " + path, error);
            return new JSONObject();
        }
    }

    /** Optional generated build asset. Missing source-checkout assets are normal; never substitute another language. */
    private JSONObject loadOptionalJsonAsset(String path) {
        try {
            return new JSONObject(new String(readAssetBytes(path, 20_000_000), StandardCharsets.UTF_8));
        } catch (Exception ignored) {
            return null;
        }
    }

    private void applyGeneratedChurchServicePack(JSONObject library, String language) {
        if (library == null || library.length() == 0) return;
        JSONObject pack = loadOptionalJsonAsset("data/church/full_services_" + language + ".json");
        if (pack == null) return;
        if (!language.equals(pack.optString("language", ""))) return;
        if (pack.optBoolean("machine_translation_used", true)) return;

        JSONArray generated = pack.optJSONArray("services");
        if (generated == null || generated.length() == 0) return;
        JSONArray services = library.optJSONArray("services");
        if (services == null) {
            services = new JSONArray();
            try { library.put("services", services); } catch (Exception ignored) { return; }
        }

        for (int i = 0; i < generated.length(); i++) {
            JSONObject overlay = generated.optJSONObject(i);
            if (overlay == null) continue;
            String id = overlay.optString("id", "").trim();
            if (id.isEmpty()) continue;
            JSONObject existing = findServiceInArray(services, id);
            if (existing == null) {
                services.put(overlay);
                continue;
            }
            java.util.Iterator<String> keys = overlay.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                try { existing.put(key, overlay.get(key)); } catch (Exception ignored) { }
            }
        }
    }

    private byte[] readAssetBytes(String path, int maxBytes) throws Exception {
        try (InputStream input = context.getAssets().open(path)) { return readLimited(input, maxBytes); }
    }

    private static HttpURLConnection open(String value, int maxBytes, boolean noCache) throws Exception {
        URL url = NetworkEndpointSecurity.requireAllowedHttps(value);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(10_000);
        connection.setReadTimeout(20_000);
        connection.setRequestMethod("GET");
        connection.setUseCaches(!noCache);
        connection.setRequestProperty("Accept", maxBytes == MAX_SIGNATURE_BYTES ? "text/plain, application/octet-stream;q=0.8" : "application/json, text/plain;q=0.9");
        connection.setRequestProperty("Accept-Encoding", "identity");
        connection.setRequestProperty("User-Agent", "OrthodoxPrayers-Android/" + BuildConfig.VERSION_NAME);
        if (noCache) {
            connection.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0");
            connection.setRequestProperty("Pragma", "no-cache");
        }
        return connection;
    }

    private static String appendQuery(String value, String parameter) {
        return value + (value.contains("?") ? "&" : "?") + parameter;
    }

    private static void validateContentType(HttpURLConnection connection) {
        String type = connection.getContentType();
        if (type == null) return;
        String normalized = type.toLowerCase();
        if (!normalized.contains("json") && !normalized.contains("text/plain") && !normalized.contains("octet-stream")) {
            throw new IllegalStateException("invalid_content_type");
        }
    }

    private static byte[] readLimited(InputStream input, int maxBytes) throws Exception {
        try (InputStream stream = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int read;
            while ((read = stream.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) throw new IllegalStateException("response_too_large");
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private static String classifyError(Exception error) {
        return RefreshErrorClassifier.classify(error);
    }

    private static String safeMessage(Exception error, String fallback) {
        if (error == null || error.getMessage() == null || error.getMessage().trim().isEmpty()) return fallback;
        return error.getMessage().replace(':', '_');
    }

    private static String sha256(byte[] payload) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(payload);
            StringBuilder value = new StringBuilder(digest.length * 2);
            for (byte item : digest) value.append(String.format("%02x", item & 0xff));
            return value.toString();
        } catch (Exception error) {
            return "";
        }
    }

    private static JSONObject newer(JSONObject first, JSONObject second) {
        if (first == null) return second;
        if (second == null) return first;
        String firstDate = first.optString("date_iso", first.optString("date", ""));
        String secondDate = second.optString("date_iso", second.optString("date", ""));
        return firstDate.compareTo(secondDate) >= 0 ? first : second;
    }

    private static boolean hasLocalizedText(JSONObject object) {
        if (object == null) return false;
        return !object.optString("ar", "").trim().isEmpty()
                || !object.optString("en", "").trim().isEmpty()
                || !object.optString("el", "").trim().isEmpty();
    }

    private String validateServices(JSONArray services) {
        String[] required = {
                "divine_liturgy",
                "vespers",
                "orthros",
                "morning_prayer",
                "evening_prayer",
                "small_compline",
                "next_sunday_full_liturgy"
        };
        java.util.HashSet<String> ids = new java.util.HashSet<>();
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (!isRenderableService(service)) return "service_content_invalid:" + i;
            String id = service.optString("id", "").trim();
            if (!ids.add(id)) return "service_duplicate:" + id;

            String baseId = service.optString("extends_service_id", "").trim();
            if (!baseId.isEmpty()) {
                JSONObject base = findServiceInArray(library().optJSONArray("services"), baseId);
                if (base == null) return "service_base_missing:" + id + ":" + baseId;
                if (!service.optString("category", "").equals(base.optString("category", ""))) {
                    return "service_base_category_mismatch:" + id;
                }
            }
        }
        for (String id : required) {
            if (!ids.contains(id)) return "service_required_missing:" + id;
        }
        return null;
    }

    private static boolean isRenderableService(JSONObject service) {
        if (service == null) return false;
        if (service.optString("id", "").trim().isEmpty()) return false;
        if (service.optString("category", "").trim().isEmpty()) return false;
        if (!hasLocalizedText(service.optJSONObject("title"))) return false;
        JSONArray segments = service.optJSONArray("segments");
        if (segments == null || segments.length() == 0) return false;
        boolean renderable = false;
        for (int i = 0; i < segments.length(); i++) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null) return false;
            String type = segment.optString("type", "text");
            JSONObject content = "section".equals(type)
                    ? segment.optJSONObject("title")
                    : segment.optJSONObject("text");
            if (!hasLocalizedText(content)) return false;
            renderable = true;
        }
        return renderable;
    }

    /** Explicit source-quality blocks take precedence over structurally renderable OCR. */
    private static boolean isUserDisplayableService(JSONObject service) {
        return service != null && (!service.has("displayable") || service.optBoolean("displayable", true));
    }

    private static JSONObject findServiceInArray(JSONArray array, String id) {
        if (array == null || id == null) return null;
        for (int i = 0; i < array.length(); i++) {
            JSONObject service = array.optJSONObject(i);
            if (service != null && id.equals(service.optString("id")) && isRenderableService(service)) return service;
        }
        return null;
    }

    private JSONObject resolveService(JSONObject service) {
        if (service == null) return null;
        String baseId = service.optString("extends_service_id", "").trim();
        if (baseId.isEmpty()) {
            try {
                JSONObject resolved = new JSONObject(service.toString());
                JSONArray segments = service.optJSONArray("segments");
                if (segments == null) return resolved;
                JSONArray resolvedSegments = applyDynamicSlotReplacements(
                        new JSONArray(segments.toString()),
                        null,
                        null,
                        preferences.effectiveLanguage()
                );
                pruneUnresolvedOrEmptySegments(resolvedSegments);
                if ("church_service".equals(service.optString("category", ""))) {
                    resolveChurchServiceScripture(resolvedSegments, preferences.effectiveLanguage());
                }
                resolved.put("segments", resolvedSegments);
                return resolved;
            } catch (Exception error) {
                Log.w(TAG, "Could not resolve static dynamic slots " + service.optString("id"), error);
                return service;
            }
        }

        JSONObject base = findServiceInArray(library().optJSONArray("services"), baseId);
        if (base == null) return service;
        try {
            JSONObject resolved = new JSONObject(base.toString());
            Iterator<String> keys = service.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                if ("segments".equals(key) || "extends_service_id".equals(key)) continue;
                resolved.put(key, deepCopyJson(service.opt(key)));
            }

            JSONArray resolvedBaseSegments = new JSONArray(base.optJSONArray("segments").toString());
            JSONObject effectiveSlots = service.optJSONObject("slot_replacements");
            if (effectiveSlots == null) {
                effectiveSlots = legacyDynamicSlots(service.optJSONObject("segment_replacements"));
            }
            JSONObject effectiveInlineSlots = service.optJSONObject("slot_inline_replacements");
            if (effectiveInlineSlots == null) {
                effectiveInlineSlots = legacyDynamicInlineSlots(service.optJSONObject("inline_replacements"));
            }
            resolvedBaseSegments = applyDynamicSlotReplacements(
                    resolvedBaseSegments,
                    effectiveSlots,
                    effectiveInlineSlots,
                    preferences.effectiveLanguage()
            );
            applySegmentReplacements(
                    resolvedBaseSegments,
                    service.optJSONObject("segment_replacements"),
                    service.optJSONObject("inline_replacements")
            );
            pruneUnresolvedOrEmptySegments(resolvedBaseSegments);
            JSONArray merged = new JSONArray();
            if ("divine_liturgy".equals(baseId)) {
                appendDailyLiturgyOverlay(merged, service.optJSONArray("segments"));
            } else {
                appendSegments(merged, service.optJSONArray("segments"));
            }
            appendSegments(merged, resolvedBaseSegments);
            resolved.put("segments", merged);
            resolved.remove("segment_replacements");
            resolved.remove("inline_replacements");
            resolved.remove("slot_replacements");
            resolved.remove("slot_inline_replacements");
            resolved.put("composed_from", baseId);
            return resolved;
        } catch (Exception error) {
            Log.w(TAG, "Could not compose daily service overlay " + service.optString("id"), error);
            return service;
        }
    }

    private void resolveChurchServiceScripture(JSONArray segments, String language) {
        if (segments == null || language == null) return;
        for (int i = 0; i < segments.length(); i++) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null || "section".equals(segment.optString("type", ""))) continue;
            String reference = segment.optString("canonical_reference", "").trim();
            if (reference.isEmpty()) continue;
            try {
                BibleCorpusRepository.ResolvedPassage passage = bibleCorpusRepository.resolve(language, reference);
                if (passage == null || passage.text == null || passage.text.trim().isEmpty()) continue;
                JSONObject text = segment.optJSONObject("text");
                if (text == null) text = new JSONObject();
                String prefix = text.optString(language, "").trim();
                String merged = prefix.isEmpty() ? passage.text : prefix + "\n\n" + passage.text;
                text.put(language, merged);
                segment.put("text", text);
                segment.put("scripture_source_id", passage.sourceId);
                segment.put("scripture_verse_count", passage.verseCount);
            } catch (Exception error) {
                Log.w(TAG, "Could not resolve fixed church-service Scripture " + reference, error);
            }
        }
    }

    private static void appendDailyLiturgyOverlay(JSONArray target, JSONArray source) throws Exception {
        if (source == null) return;
        for (int i = 0; i < source.length(); i++) {
            JSONObject segment = source.optJSONObject(i);
            if (segment == null) continue;
            JSONObject copy = new JSONObject(segment.toString());
            if ("note".equals(copy.optString("type", ""))) {
                JSONObject text = copy.optJSONObject("text");
                String ar = text == null ? "" : text.optString("ar", "").trim();
                String en = text == null ? "" : text.optString("en", "").trim();
                String el = text == null ? "" : text.optString("el", "").trim();
                boolean dayFacts = ar.startsWith("التاريخ المدني:")
                        || en.startsWith("Civil date:")
                        || el.startsWith("Πολιτικὴ ἡμερομηνία:");
                if (!dayFacts) continue;
                copy.put("type", "text");
                copy.remove("collapsed_by_default");
                copy.put("speaker", new JSONObject()
                        .put("ar", "اليوم الكنسي")
                        .put("en", "Church day")
                        .put("el", "Ἐκκλησιαστικὴ ἡμέρα"));
            }
            target.put(copy);
        }
    }

    private static boolean isFollowAlongLiturgy(JSONObject service) {
        if (service == null) return false;
        String id = service.optString("id", "");
        String composedFrom = service.optString("composed_from", "");
        return "divine_liturgy".equals(id)
                || "divine_liturgy".equals(composedFrom)
                || "divine_liturgy_basil".equals(id)
                || "divine_liturgy_basil".equals(composedFrom)
                || "presanctified_liturgy".equals(id)
                || "presanctified_liturgy".equals(composedFrom)
                || service.optString("publication_status", "")
                .startsWith("DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END");
    }

    /**
     * Builds one continuous reader without duplicating any religious text in assets.
     *
     * The reader contains only the appointed Divine Liturgy itself. Orthros, Hours,
     * Proskomide, personal Communion preparation and thanksgiving remain separate.
     * Daily metadata is exposed outside the prayer-text stream.
     */
    private JSONObject composeFollowAlongLiturgy(JSONObject liturgy) {
        if (liturgy == null || liturgy.optBoolean("follow_along_composed", false)) return liturgy;
        try {
            JSONObject result = new JSONObject(liturgy.toString());
            String language = preferences.effectiveLanguage();
            JSONArray core = strictAppointedLiturgyCore(
                    liturgy.optJSONArray("segments"),
                    language
            );
            JSONArray continuous = new JSONArray();
            appendLiturgyDayHeader(continuous, liturgy);
            appendSegments(continuous, core);

            // R56: the Liturgy reader is intentionally strict. Matins, the Hours,
            // Proskomide, personal pre-Communion prayers and thanksgiving are
            // separate offices. They must never be merged into the appointed
            // Divine Liturgy and then presented as though they belonged to its
            // fixed order.
            result.put("segments", continuous);
            result.put("follow_along_composed", true);
            result.put("follow_along_mode", "STRICT_APPOINTED_LITURGY_CORE_ONLY");
            result.put("full_service_scope", "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL");
            result.put("full_service_phase_count", 1);
            result.put("adjacent_offices_separate", true);
            result.put("excluded_from_liturgy_core", new JSONArray()
                    .put("orthros")
                    .put("hours")
                    .put("proskomide")
                    .put("pre_communion_prayers")
                    .put("thanksgiving_after_communion"));
            result.put("silent_prayer_contract", silentPrayerContract(core));
            // Never upgrade a blocked/partial native edition merely because the
            // reader successfully filtered its segments.
            result.put("full_service_complete", liturgy.optBoolean("full_service_complete", false));
            return result;
        } catch (Exception error) {
            Log.w(TAG, "Could not compose strict appointed Liturgy", error);
            return liturgy;
        }
    }

    private static void appendLiturgyDayHeader(JSONArray target, JSONObject liturgy) throws Exception {
        if (target == null || liturgy == null || liturgy.optString("dynamic_date", "").trim().isEmpty()) return;
        target.put(new JSONObject()
                .put("type", "section")
                .put("editorial_metadata_only", true)
                .put("title", new JSONObject()
                        .put("ar", "قداس اليوم الكامل")
                        .put("en", "Today’s complete Divine Liturgy")
                        .put("el", "Ἡ πλήρης σημερινὴ Θεία Λειτουργία")));
        JSONObject summary = liturgy.optJSONObject("summary");
        if (summary != null) {
            target.put(new JSONObject()
                    .put("type", "text")
                    .put("editorial_metadata_only", true)
                    .put("speaker", new JSONObject()
                            .put("ar", "تذكار اليوم والصيام")
                            .put("en", "Today’s commemoration and fasting")
                            .put("el", "Μνήμη καὶ νηστεία τῆς ἡμέρας"))
                    .put("text", deepCopyJson(summary)));
        }
    }

    private static JSONObject silentPrayerContract(JSONArray segments) throws Exception {
        int priest = 0;
        int faithful = 0;
        if (segments != null) {
            for (int i = 0; i < segments.length(); i++) {
                JSONObject segment = segments.optJSONObject(i);
                if (segment == null || !"silent".equals(segment.optString("delivery", ""))) continue;
                if ("faithful".equals(segment.optString("delivery_actor", ""))) faithful++;
                else priest++;
            }
        }
        return new JSONObject()
                .put("source_marked_only", true)
                .put("priest_silent_prayers", priest)
                .put("faithful_private_prayers", faithful)
                .put("spoken_responses_kept_separate", true);
    }

    private static JSONArray strictAppointedLiturgyCore(JSONArray source, String language) throws Exception {
        JSONArray output = new JSONArray();
        if (source == null) return output;
        for (int i = 0; i < source.length(); i++) {
            JSONObject segment = source.optJSONObject(i);
            if (segment == null) continue;
            JSONObject copy = new JSONObject(segment.toString());

            // The Matins Gospel belongs to Orthros, even when an older source
            // edition printed it immediately before the Liturgy booklet.
            if ("matins_gospel".equals(copy.optString("dynamic_slot", ""))) continue;
            if ("matins_gospel".equals(copy.optString("follow_along_phase", ""))) continue;
            if (isDailyLiturgyMetadataSegment(copy, language)) continue;
            if ("section".equals(copy.optString("type", ""))) {
                JSONObject title = copy.optJSONObject("title");
                String value = title == null ? "" : title.optString(language, "").trim();
                if (isMatinsHeading(value, language)) continue;
                if (copy.optBoolean("follow_along_phase", false)) continue;
            }
            output.put(copy);
        }
        return output;
    }

    private static boolean isDailyLiturgyMetadataSegment(JSONObject segment, String language) {
        if (segment == null) return false;
        JSONObject speaker = segment.optJSONObject("speaker");
        String speakerValue = speaker == null ? "" : speaker.optString(language, "").trim();
        if ("ar".equals(language) && "اليوم الكنسي".equals(speakerValue)) return true;
        if ("en".equals(language) && "Church day".equals(speakerValue)) return true;
        if ("el".equals(language) && "Ἐκκλησιαστικὴ ἡμέρα".equals(speakerValue)) return true;
        if (!"section".equals(segment.optString("type", ""))) return false;
        JSONObject title = segment.optJSONObject("title");
        String value = title == null ? "" : title.optString(language, "").trim();
        if ("ar".equals(language)) return value.contains("خدمة اليوم") || value.contains("قراءات وقطع اليوم");
        if ("el".equals(language)) return value.contains("σημερινὴ ἀκολουθία") || value.contains("Ἀναγνώσματα καὶ ὕμνοι");
        String upper = value.toUpperCase(Locale.ROOT);
        return upper.contains("TODAY’S SERVICE") || upper.contains("TODAY'S SERVICE")
                || upper.contains("READINGS AND HYMNS OF THE DAY");
    }

    private static boolean isMatinsHeading(String value, String language) {
        if (value == null || value.isEmpty()) return false;
        if ("ar".equals(language)) return value.contains("إنجيل السَحَر") || value.contains("إنجيل السحر");
        if ("el".equals(language)) return value.contains("ΕΩΘΙΝΟΝ ΕΥΑΓΓΕΛΙΟΝ")
                || value.contains("Ἑωθινὸν Εὐαγγέλιον");
        return value.toUpperCase(Locale.ROOT).contains("MATINS GOSPEL");
    }

    private static JSONArray thanksgivingSegmentsForLiturgy(
            JSONObject thanksgiving,
            String language,
            String liturgyId
    ) throws Exception {
        JSONArray source = thanksgiving == null ? null : thanksgiving.optJSONArray("segments");
        JSONArray output = new JSONArray();
        if (source == null) return output;

        String selected = normalizeLiturgyVariant(liturgyId);
        String activeArabicVariant = "";
        boolean suppressNextGreekTroparion = false;

        for (int i = 0; i < source.length(); i++) {
            JSONObject segment = source.optJSONObject(i);
            if (segment == null) continue;
            JSONObject copy = new JSONObject(segment.toString());
            String type = copy.optString("type", "text");
            JSONObject titleObject = copy.optJSONObject("title");
            String title = titleObject == null ? "" : titleObject.optString(language, "").trim();

            if ("ar".equals(language)) {
                String branch = arabicThanksgivingVariant(title);
                if (!branch.isEmpty()) {
                    activeArabicVariant = branch;
                    if (branch.equals(selected)) {
                        copy.put("title", new JSONObject()
                                .put("ar", arabicThanksgivingTitle(branch))
                                .put("en", "")
                                .put("el", ""));
                        output.put(copy);
                    }
                    continue;
                }
                if (!activeArabicVariant.isEmpty()) {
                    if ("note".equals(type)) continue;
                    if ("text".equals(type)) {
                        if (activeArabicVariant.equals(selected)) output.put(copy);
                        activeArabicVariant = "";
                        continue;
                    }
                }
            }

            // The current Greek pack contains the St John dismissal troparion only.
            // Never show it inside the Basil or Presanctified service as though it
            // belonged to that Liturgy. Common thanksgiving prayers remain visible.
            if ("el".equals(language)) {
                if ("section".equals(type) && "Ἀπολυτίκια".equals(title)) {
                    suppressNextGreekTroparion = !"divine_liturgy".equals(selected);
                    if (suppressNextGreekTroparion) continue;
                } else if (suppressNextGreekTroparion && "text".equals(type)) {
                    suppressNextGreekTroparion = false;
                    continue;
                }
            }
            output.put(copy);
        }
        return output;
    }

    private static String normalizeLiturgyVariant(String serviceId) {
        String id = serviceId == null ? "" : serviceId.trim();
        if (id.contains("basil")) return "divine_liturgy_basil";
        if (id.contains("presanctified")) return "presanctified_liturgy";
        return "divine_liturgy";
    }

    private static String arabicThanksgivingVariant(String title) {
        if (title == null) return "";
        if (title.contains("يوحنا الذهبي")) return "divine_liturgy";
        if (title.contains("باسيليوس الكبير")) return "divine_liturgy_basil";
        if (title.contains("السابق تقديسه")) return "presanctified_liturgy";
        return "";
    }

    private static String arabicThanksgivingTitle(String variant) {
        if ("divine_liturgy_basil".equals(variant)) return "طروبارية القديس باسيليوس الكبير";
        if ("presanctified_liturgy".equals(variant)) return "طروبارية القديس غريغوريوس الكبير";
        return "طروبارية القديس يوحنا الذهبي الفم";
    }

    private void appendNativePrayerService(JSONArray target, String serviceId, String language) {
        JSONObject service = findServiceInArray(library().optJSONArray("services"), serviceId);
        if (hasNativePrayerText(service, language)) appendSegments(target, service.optJSONArray("segments"));
    }

    private static boolean hasNativePrayerText(JSONObject service, String language) {
        JSONArray segments = service == null ? null : service.optJSONArray("segments");
        if (segments == null) return false;
        for (int i = 0; i < segments.length(); i++) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null || !"text".equals(segment.optString("type", "text"))) continue;
            // A note that only reports missing/pending content is not a prayer and
            // must never make an otherwise empty service appear complete.
            if (segment.optBoolean("collapsed_by_default", false)
                    || "note".equals(segment.optString("type", ""))) continue;
            JSONObject text = segment.optJSONObject("text");
            if (text != null && !text.optString(language, "").trim().isEmpty()) return true;
        }
        return false;
    }

    private static JSONObject followAlongSection(String ar, String en, String el) throws Exception {
        return new JSONObject()
                .put("type", "section")
                .put("follow_along_phase", true)
                .put("title", new JSONObject().put("ar", ar).put("en", en).put("el", el));
    }

    private static void applySegmentReplacements(JSONArray segments, JSONObject exact, JSONObject inline) {
        if (segments == null) return;
        for (int i = 0; i < segments.length(); i++) {
            Object value = segments.opt(i);
            applyReplacementsToValue(value, exact, inline);
        }
    }

    private static JSONArray applyDynamicSlotReplacements(
            JSONArray segments,
            JSONObject replacements,
            JSONObject inlineReplacements,
            String language
    ) throws Exception {
        if (segments == null) return new JSONArray();
        JSONArray output = new JSONArray();
        for (int i = 0; i < segments.length(); i++) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null) continue;
            JSONObject copy = new JSONObject(segment.toString());
            String inlineSlot = copy.optString("dynamic_inline_slot", "");
            String inlineMarker = copy.optString("dynamic_inline_marker", "");
            if (!inlineSlot.isEmpty() && !inlineMarker.isEmpty()) {
                JSONObject replacement = inlineReplacements == null
                        ? null : inlineReplacements.optJSONObject(inlineSlot);
                JSONObject text = copy.optJSONObject("text");
                String current = text == null ? "" : text.optString(language, "");
                String selected = replacement == null ? "" : replacement.optString(language, "").trim();
                if (selected.isEmpty()) selected = defaultInlineSlotValue(inlineSlot, language);
                if (!current.isEmpty() && !selected.isEmpty()) {
                    text.put(language, current.replace(inlineMarker, selected));
                }
            }

            String slot = copy.optString("dynamic_slot", "");
            JSONObject replacement = replacements == null ? null : replacements.optJSONObject(slot);
            String selected = replacement == null ? "" : replacement.optString(language, "").trim();
            String mode = copy.optString("dynamic_slot_mode", "replace");
            if ("replace_group_if_present".equals(mode)) {
                // Seasonal antiphons and the Trisagion are groups, not one-line
                // placeholders. Keep every word of the ordinary native edition
                // when no verified variant exists. When a verified replacement
                // is present, suppress the entire ordinary group and emit the
                // replacement only at the segment explicitly marked as its
                // liturgically correct position.
                if (selected.isEmpty()) {
                    output.put(copy);
                } else if (copy.optBoolean("dynamic_slot_group_emit", false)) {
                    copy.put("text", isolatedLocalizedText(selected, language));
                    copy.put("resolved_dynamic_slot", slot);
                    copy.put("resolved_dynamic_slot_group",
                            copy.optString("dynamic_slot_group", slot));
                    output.put(copy);
                }
            } else if ("replace".equals(mode)) {
                if (!slot.isEmpty()) copy.put("text", isolatedLocalizedText(selected, language));
                output.put(copy);
            } else if ("replace_if_present".equals(mode)) {
                // Keep the ordinary fixed text (for example the Sunday Communion
                // hymn) unless the signed daily layer supplies a feast-specific one.
                if (!slot.isEmpty() && !selected.isEmpty()) {
                    copy.put("text", isolatedLocalizedText(selected, language));
                    copy.put("resolved_dynamic_slot", slot);
                }
                output.put(copy);
            } else {
                output.put(copy);
                if (!slot.isEmpty() && !selected.isEmpty()) {
                    JSONObject inserted = new JSONObject();
                    inserted.put("type", "text");
                    inserted.put("speaker", deepCopyJson(copy.optJSONObject("dynamic_slot_speaker")));
                    inserted.put("text", isolatedLocalizedText(selected, language));
                    inserted.put("resolved_dynamic_slot", slot);
                    output.put(inserted);
                }
            }
        }
        return output;
    }

    private static String defaultInlineSlotValue(String slot, String language) {
        if (!"gospel_evangelist_name".equals(slot)) return "";
        if ("en".equals(language)) return "Evangelist";
        if ("el".equals(language)) return "Εὐαγγελιστής";
        return "الإنجيلي";
    }

    /**
     * R19 signed snapshots used Arabic template markers. Convert their already
     * verified localized values into R20 semantic slots in memory, so installed
     * clients gain English/Greek Liturgy insertion without rewriting signed bytes.
     */
    private static JSONObject legacyDynamicSlots(JSONObject legacy) throws Exception {
        JSONObject slots = new JSONObject();
        if (legacy == null) return slots;
        copyLegacySlot(legacy, slots, "[طروبارية اليوم]", "daily_troparion");
        copyLegacySlot(
                legacy,
                slots,
                "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]",
                "church_troparion"
        );
        copyLegacySlot(legacy, slots, "[القنداق]", "daily_kontakion");
        copyLegacySlot(legacy, slots, "[البروكيمنن]", "prokeimenon");
        copyLegacySlot(legacy, slots, "[فصل من رسالة اليوم]", "epistle");
        copyLegacySlot(legacy, slots, "[فصل الإنجيل المعيّن لهذا اليوم]", "gospel");
        copyLegacySlot(legacy, slots, "[آية المناولة]", "communion_hymn");

        JSONObject hymns = new JSONObject();
        for (String language : new String[]{"ar", "en", "el"}) {
            StringBuilder combined = new StringBuilder();
            for (String slot : new String[]{"daily_troparion", "church_troparion", "daily_kontakion"}) {
                JSONObject value = slots.optJSONObject(slot);
                String text = value == null ? "" : value.optString(language, "").trim();
                if (text.isEmpty()) continue;
                if (combined.length() > 0) combined.append("\n\n");
                combined.append(text);
            }
            hymns.put(language, combined.toString());
        }
        slots.put("daily_hymns", hymns);
        return slots;
    }

    private static void copyLegacySlot(
            JSONObject legacy,
            JSONObject slots,
            String marker,
            String slot
    ) throws Exception {
        JSONObject value = legacy.optJSONObject(marker);
        if (value != null) slots.put(slot, new JSONObject(value.toString()));
    }

    private static JSONObject legacyDynamicInlineSlots(JSONObject legacy) throws Exception {
        JSONObject slots = new JSONObject();
        if (legacy == null) return slots;
        JSONObject evangelist = legacy.optJSONObject("[اسم الإنجيلي]");
        if (evangelist != null) {
            slots.put("gospel_evangelist_name", new JSONObject(evangelist.toString()));
        }
        return slots;
    }

    private static JSONObject isolatedLocalizedText(String selected, String language) throws Exception {
        JSONObject value = new JSONObject();
        for (String candidate : new String[]{"ar", "en", "el"}) {
            value.put(candidate, candidate.equals(language) ? selected : "");
        }
        return value;
    }

    /**
     * Removes legacy placeholder rows after the signed daily overlay is composed.
     * An absent optional proper must disappear; it must never render as an empty
     * reader/chanter row or as an old bracketed marker from the static template.
     */
    private static void pruneUnresolvedOrEmptySegments(JSONArray segments) {
        if (segments == null) return;
        for (int i = segments.length() - 1; i >= 0; i--) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null) continue;
            JSONObject text = segment.optJSONObject("text");
            if (text == null) continue;
            boolean hasVisibleText = false;
            boolean hasUnresolvedMarker = false;
            boolean onlyLegacyUnavailableCopy = true;
            for (String language : new String[]{"ar", "en", "el"}) {
                String value = text.optString(language, "").trim();
                if (!value.isEmpty()) {
                    hasVisibleText = true;
                    if (!isLegacyUnavailableText(value)) onlyLegacyUnavailableCopy = false;
                }
                if (isLegacyPlaceholderMarker(value)) hasUnresolvedMarker = true;
            }
            if (!hasVisibleText || hasUnresolvedMarker || onlyLegacyUnavailableCopy) segments.remove(i);
        }

        // Remove section headings that no longer have content before the next heading.
        for (int i = segments.length() - 1; i >= 0; i--) {
            JSONObject segment = segments.optJSONObject(i);
            if (segment == null || !"section".equals(segment.optString("type"))) continue;
            boolean hasContent = false;
            for (int j = i + 1; j < segments.length(); j++) {
                JSONObject next = segments.optJSONObject(j);
                if (next == null) continue;
                if ("section".equals(next.optString("type"))) break;
                if (next.optJSONObject("text") != null) { hasContent = true; break; }
            }
            if (!hasContent) segments.remove(i);
        }
    }

    private static boolean isLegacyPlaceholderMarker(String value) {
        String normalized = value == null ? "" : value.trim();
        return normalized.equals("[طروبارية اليوم]")
                || normalized.equals("[طروبارية صاحب الكنيسة أو القديس إن وُجدت]")
                || normalized.equals("[القنداق]")
                || normalized.equals("[البروكيمنن]")
                || normalized.equals("[فصل من رسالة اليوم]")
                || normalized.equals("[فصل الإنجيل المعيّن لهذا اليوم]")
                || normalized.equals("[آية المناولة]");
    }

    private static boolean isLegacyUnavailableText(String value) {
        String normalized = value == null ? "" : value.toLowerCase(Locale.ROOT);
        return normalized.contains("غير متاح")
                || normalized.contains("لم يتوفر نص")
                || normalized.contains("لن يعرض التطبيق نص")
                || normalized.contains("currently unavailable")
                || normalized.contains("not available")
                || normalized.contains("will not display guessed")
                || normalized.contains("δεν είναι διαθέσιμο")
                || normalized.contains("δὲν εἶναι διαθέσιμο");
    }

    private static void applyReplacementsToValue(Object value, JSONObject exact, JSONObject inline) {
        if (value instanceof JSONObject) {
            JSONObject object = (JSONObject) value;
            if (object.has("ar") && (object.has("en") || object.has("el"))) {
                String arabic = object.optString("ar", "");
                JSONObject replacement = exact == null ? null : exact.optJSONObject(arabic);
                if (replacement != null) {
                    replaceLocalizedObject(object, replacement);
                    return;
                }
                if (inline != null && !arabic.isEmpty()) {
                    Iterator<String> keys = inline.keys();
                    while (keys.hasNext()) {
                        String marker = keys.next();
                        JSONObject localizedReplacement = inline.optJSONObject(marker);
                        if (localizedReplacement == null || !arabic.contains(marker)) continue;
                        for (String language : new String[]{"ar", "en", "el"}) {
                            String current = object.optString(language, "");
                            String replacementText = localizedReplacement.optString(language, "");
                            if (!current.isEmpty() && !replacementText.isEmpty()) {
                                putQuietly(object, language, current.replace(marker, replacementText));
                            }
                        }
                    }
                }
                return;
            }
            Iterator<String> keys = object.keys();
            while (keys.hasNext()) applyReplacementsToValue(object.opt(keys.next()), exact, inline);
        } else if (value instanceof JSONArray) {
            JSONArray array = (JSONArray) value;
            for (int i = 0; i < array.length(); i++) applyReplacementsToValue(array.opt(i), exact, inline);
        }
    }

    private static void replaceLocalizedObject(JSONObject target, JSONObject replacement) {
        for (String language : new String[]{"ar", "en", "el"}) {
            putQuietly(target, language, replacement.optString(language, ""));
        }
    }

    private static void putQuietly(JSONObject object, String key, Object value) {
        try { object.put(key, value); }
        catch (Exception ignored) {}
    }

    private static Object deepCopyJson(Object value) {
        try {
            if (value instanceof JSONObject) return new JSONObject(value.toString());
            if (value instanceof JSONArray) return new JSONArray(value.toString());
        } catch (Exception exception) {
            Log.w(TAG, "Unable to deep-copy JSON value; using the original value", exception);
        }
        return value;
    }

    private static void appendSegments(JSONArray output, JSONArray source) {
        if (source == null) return;
        for (int i = 0; i < source.length(); i++) {
            Object value = source.opt(i);
            output.put(deepCopyJson(value));
        }
    }

    private void collectByCategory(JSONArray array, String category, Map<String, JSONObject> output) {
        if (array == null) return;
        for (int i = 0; i < array.length(); i++) {
            JSONObject service = array.optJSONObject(i);
            if (!isRenderableService(service) || !isUserDisplayableService(service)
                    || !category.equals(service.optString("category"))) continue;
            output.putIfAbsent(service.optString("id", "service-" + i), resolveService(service));
        }
    }

    private void collectAll(JSONArray array, Map<String, JSONObject> output) {
        if (array == null) return;
        for (int i = 0; i < array.length(); i++) {
            JSONObject service = array.optJSONObject(i);
            if (isRenderableService(service) && isUserDisplayableService(service)) {
                output.putIfAbsent(service.optString("id", "service-" + i), resolveService(service));
            }
        }
    }

    public static final class RefreshOutcome {
        public final RefreshResult result;
        public final String message;
        public RefreshOutcome(RefreshResult result, String message) {
            this.result = result;
            this.message = message == null ? "" : message;
        }
    }
}
