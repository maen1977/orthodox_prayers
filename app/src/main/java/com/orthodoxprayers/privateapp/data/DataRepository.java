package com.orthodoxprayers.privateapp.data;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.BuildConfig;
import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.model.LocalizedValue;

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
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class DataRepository {
    public enum RefreshResult { UPDATED, NOT_MODIFIED, FAILED }
    public enum RefreshState { IDLE, REFRESHING, UPDATED, CURRENT, FAILED }
    public interface RefreshCallback { void onComplete(RefreshResult result, String message); }

    private static final String TAG = "OrthodoxData";
    private static final int MAX_JSON_BYTES = 2_000_000;
    private static final int MAX_MANIFEST_BYTES = 64_000;
    private static final int MAX_SIGNATURE_BYTES = 16_384;
    private static final int MAX_DOWNLOAD_ATTEMPTS = 2;

    private final Context context;
    private final AppPreferences preferences;
    private DailyDataStore dataStore;
    private final boolean languageScopedStore;
    private final DataSignatureVerifier signatureVerifier;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final Object refreshGuard = new Object();

    private JSONObject today;
    private JSONObject fallbackLibrary;
    private JSONObject arabicLibrary;
    private JSONObject greekLibrary;
    private JSONObject englishLibrary;
    private JSONObject arabicSearchIndex;
    private JSONObject greekSearchIndex;
    private JSONObject englishSearchIndex;
    private JSONObject sourceRegistry;
    private JSONObject fallbackChurchDirectory;
    private JSONObject fallbackSourceHealth;
    private JSONObject fallbackServiceCoverage;
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
        this.languageScopedStore = languageScopedStore;
        preferences.clearLegacyRemoteCache();
        fallbackLibrary = loadJsonAsset("data/library.json");
        arabicLibrary = loadJsonAsset("data/native/library_ar.json");
        greekLibrary = loadJsonAsset("data/native/library_el.json");
        englishLibrary = loadJsonAsset("data/native/library_en.json");
        arabicSearchIndex = loadJsonAsset("data/search/search_index_ar.json");
        greekSearchIndex = loadJsonAsset("data/search/search_index_el.json");
        englishSearchIndex = loadJsonAsset("data/search/search_index_en.json");
        sourceRegistry = loadJsonAsset("data/source_registry.json");
        fallbackChurchDirectory = loadJsonAsset("data/churches.json");
        fallbackSourceHealth = loadJsonAsset("data/source_health.json");
        fallbackServiceCoverage = loadJsonAsset("data/service_coverage.json");
        today = loadBestToday();
    }

    public synchronized JSONObject today() { return today; }
    public JSONObject library() {
        return libraryForLanguage(preferences.effectiveLanguage());
    }

    private JSONObject libraryForLanguage(String language) {
        JSONObject selected;
        if ("en".equals(language)) selected = englishLibrary;
        else if ("el".equals(language)) selected = greekLibrary;
        else selected = arabicLibrary;
        // Never fall back to another language or to the legacy mixed library.
        // Missing native assets are shown as unavailable rather than substituted.
        return selected != null ? selected : new JSONObject();
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

    /** Metadata may safely fall back to the official proper name; religious text never does. */
    public String metadataLocalized(JSONObject value, String fallback) {
        if (value == null) return fallback == null ? "" : fallback;
        String language = preferences.effectiveLanguage();
        String selected = value.optString(language, "").trim();
        if (!selected.isEmpty()) return selected;
        String arabic = value.optString("ar", "").trim();
        if (!arabic.isEmpty()) return arabic;
        String english = value.optString("en", "").trim();
        return english.isEmpty() ? (fallback == null ? "" : fallback) : english;
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
        if (languageScopedStore) {
            dataStore = new DailyDataStore(context, preferences.effectiveLanguage());
        }
        loadedStoredSource = "";
        loadedStoredHash = "";
        loadError = "";
        today = loadBestToday();
    }

    public java.util.List<String> availableCachedDates() {
        return dataStore.availableDates();
    }

    public String local(String ar, String en, String el) {
        String language = preferences.effectiveLanguage();
        if ("en".equals(language)) return en;
        if ("el".equals(language)) return el;
        return ar;
    }

    public LocalizedValue localizedValue(JSONObject object, String fallback) {
        String language = preferences.effectiveLanguage();
        if (object == null) return new LocalizedValue(fallback, false);

        String arabic = object.optString("ar", "").trim();
        String requested = object.optString(language, "").trim();
        if ("ar".equals(language)) {
            if (!requested.isEmpty()) return new LocalizedValue(requested, false);
            return new LocalizedValue(fallback, false);
        }

        if (TranslationCoverage.isValidTargetText(requested, arabic, language)) {
            return new LocalizedValue(requested, false);
        }

        String safeFallback = fallback == null ? "" : fallback.trim();
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

    public JSONObject searchIndex() {
        String language = preferences.effectiveLanguage();
        if ("en".equals(language)) return englishSearchIndex;
        if ("el".equals(language)) return greekSearchIndex;
        return arabicSearchIndex;
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
        // Never compose a service for today with a stale signed overlay. The
        // static service remains available, but yesterday's Epistle/Gospel are
        // not allowed to appear under today's date.
        JSONObject dynamic = isTodayCurrent()
                ? findServiceInArray(today().optJSONArray("services"), id)
                : null;
        JSONObject selected = dynamic != null ? dynamic : findServiceInArray(library().optJSONArray("services"), id);
        if (selected == null) {
            JSONObject index = searchIndex();
            selected = index == null ? null : findServiceInArray(index.optJSONArray("reader_services"), id);
        }
        return resolveService(selected);
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
        if (index != null) collectAll(index.optJSONArray("reader_services"), unique);
        return new ArrayList<>(unique.values());
    }

    /** Coverage of the requested native pack, independent of the language currently open in the UI. */
    public TranslationCoverage.Result nativeContentCoverage(String language) {
        return TranslationCoverage.measure(libraryForLanguage(language), language);
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
                outcome = new RefreshOutcome(RefreshResult.FAILED, "unexpected_refresh_error");
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

    private RefreshOutcome performRefresh(boolean forceFullDownload) {
        String configuredTodayUrl = context.getString(R.string.data_source_url).trim();
        String configuredTodaySignatureUrl = context.getString(R.string.data_signature_url).trim();
        String configuredManifestUrl = context.getString(R.string.update_manifest_url).trim();
        String configuredManifestSignatureUrl = context.getString(R.string.update_manifest_signature_url).trim();
        if (configuredTodayUrl.isEmpty()) {
            return new RefreshOutcome(RefreshResult.FAILED, "data_url_missing");
        }

        UpdateManifest.Selection manifestSelection = null;
        Exception manifestError = null;
        if (!configuredManifestUrl.isEmpty() && !configuredManifestSignatureUrl.isEmpty()) {
            try {
                manifestSelection = downloadManifestSelection(
                        configuredManifestUrl,
                        configuredManifestSignatureUrl
                );
            } catch (Exception error) {
                manifestError = error;
                Log.w(TAG, "Signed update manifest was unavailable; using signed endpoint fallbacks", error);
                String message = error.getMessage() == null ? "" : error.getMessage();
                if (message.startsWith("app_update_required")
                        || message.startsWith("manifest_revision_rollback")) {
                    return new RefreshOutcome(RefreshResult.FAILED, message);
                }
                String expectedDate = currentAmmanDate();
                if (preferences.acceptedManifestRevisionForDate(expectedDate) > 0L) {
                    return new RefreshOutcome(
                            RefreshResult.FAILED,
                            "manifest_unavailable_after_acceptance"
                    );
                }
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
        for (String jsonUrl : DailyDataEndpointPolicy.jsonCandidates(
                configuredTodayUrl,
                currentAmmanDate(),
                preferences.effectiveLanguage()
        )) {
            String signatureUrl = DailyDataEndpointPolicy.signatureUrl(
                    configuredTodayUrl,
                    configuredTodaySignatureUrl,
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
            String validationError = validate(parsed, currentAmmanDate(), true);
            if (validationError != null) throw new IllegalStateException(validationError);
            String translationError = VerifiedContentSanitizer.firstUnsafeTranslationError(parsed);
            if (!translationError.isEmpty()) throw new IllegalStateException(translationError);
            // Defense in depth: strict payloads should be unchanged by this sanitizer.
            VerifiedContentSanitizer.sanitize(parsed);

            dataStore.saveVerified(jsonBytes, signatureBytes);
            String newEtag = connection.getHeaderField("ETag");
            long now = System.currentTimeMillis();
            preferences.saveRemoteMetadata(newEtag, jsonUrl, now);
            if (manifestRevision > 0L) {
                preferences.saveAcceptedManifest(currentAmmanDate(), manifestRevision);
            }
            synchronized (this) { today = parsed; }
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
        if (data == null || data.length() == 0) return "payload_empty";
        if (!DataContract.supportsSchema(data.optInt("schema_version", 0))) return "schema_unsupported";
        String date = data.optString("date_iso", data.optString("date", ""));
        if (date.trim().isEmpty()) return "date_missing";
        try {
            LocalDate parsedDate = LocalDate.parse(date);
            LocalDate ammanToday = LocalDate.parse(currentAmmanDate());
            if (parsedDate.isAfter(ammanToday)) return "date_in_future:" + date;
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

    public static boolean isRetryableRefreshMessage(String message) {
        String value = message == null ? "" : message;
        return value.startsWith("network_")
                || value.startsWith("http_")
                || value.startsWith("date_not_ready")
                || value.startsWith("signature_http_")
                || value.startsWith("manifest_unavailable_after_acceptance");
    }

    public String userFacingRefreshStatus() {
        if (isRefreshing()) return local("جارٍ تحديث بيانات اليوم تلقائيًا…", "Updating today’s data automatically…", "Αὐτόματη ἐνημέρωση δεδομένων…");
        String code = refreshMessage == null || refreshMessage.isEmpty() ? preferences.lastRefreshMessage() : refreshMessage;
        if (code == null || code.isEmpty()) {
            if (hasUsableCurrentData()) return local("بيانات اليوم جاهزة", "Today’s data is ready", "Τὰ σημερινὰ δεδομένα εἶναι ἕτοιμα");
            return local("بانتظار تحديث بيانات اليوم", "Waiting for today’s data update", "Ἀναμονὴ σημερινῶν δεδομένων");
        }
        if ("updated".equals(code) || "updated_signed".equals(code) || "updated_via_manifest".equals(code)) return local("تم تحديث بيانات اليوم والتحقق من توقيعها", "Today’s data was updated and its signature verified", "Τὰ δεδομένα ἐνημερώθηκαν καὶ ἐπαληθεύθηκαν");
        if ("not_modified".equals(code) || "manifest_not_modified".equals(code)) return local("بيانات اليوم محدثة بالفعل", "Today’s data is already current", "Τὰ δεδομένα εἶναι ἤδη ἐνημερωμένα");
        if ("refresh_in_progress".equals(code) || "refreshing".equals(code)) return local("التحديث جارٍ الآن", "An update is already in progress", "Ἡ ἐνημέρωση βρίσκεται σὲ ἐξέλιξη");
        if (code.startsWith("app_update_required")) return local("يلزم تحديث إصدار التطبيق لقراءة بيانات اليوم الجديدة", "The app must be updated to read today’s new data", "Απαιτεῖται νεότερη ἔκδοση τῆς ἐφαρμογῆς");
        if (code.startsWith("manifest_revision_rollback")) return local("رُفض إصدار بيانات أقدم حفاظًا على سلامة التحديث", "An older data revision was rejected for update safety", "Ἀπορρίφθηκε παλαιότερη ἀναθεώρηση δεδομένων");
        if (code.startsWith("manifest_unavailable_after_acceptance")) return local("تعذر التحقق من بيان التحديث الآمن؛ ستبقى آخر نسخة موثوقة ظاهرة", "The secure update manifest could not be verified; the last trusted copy remains in use", "Τὸ ἀσφαλὲς δηλωτικὸ ἐνημέρωσης δὲν ἐπαληθεύθηκε");
        if (code.startsWith("date_not_ready")) return local("لم تُنشر بيانات تاريخ اليوم على الخادم بعد؛ تظهر آخر نسخة سليمة", "Today’s server data is not published yet; the last valid copy is shown", "Τὰ σημερινὰ δεδομένα δὲν δημοσιεύθηκαν ἀκόμη");
        if (code.startsWith("http_")) return local("تعذر الوصول إلى خادم التحديث", "The update server could not be reached", "Ὁ διακομιστὴς ἐνημέρωσης δὲν εἶναι διαθέσιμος");
        if (code.startsWith("network_")) return local("لا يوجد اتصال صالح بالإنترنت الآن", "No usable internet connection is available", "Δὲν ὑπάρχει διαθέσιμη σύνδεση");
        if (code.contains("signature")) return local("فشل التوقيع الرقمي للتحديث وتم رفضه؛ تظهر آخر نسخة موثوقة", "The update signature failed and was rejected; the last trusted copy is shown", "Ἡ ψηφιακὴ ὑπογραφὴ ἀπέτυχε");
        if (code.startsWith("invalid_")) return local("وصلت بيانات ناقصة أو غير صالحة وتم تجاهلها", "Incomplete or invalid data was received and ignored", "Ἐλήφθησαν ἐλλιπῆ δεδομένα");
        if (preferences.lastRefreshSucceeded()) return local("اكتمل آخر فحص للتحديث بنجاح", "The last update check completed successfully", "Ὁ τελευταῖος ἔλεγχος ὁλοκληρώθηκε");
        return local("تعذر التحديث؛ تظهر آخر نسخة سليمة محفوظة", "Update failed; the last valid saved copy is shown", "Ἡ ἐνημέρωση ἀπέτυχε");
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
        if (validationError != null) throw new IllegalStateException(validationError);
        String translationError = VerifiedContentSanitizer.firstUnsafeTranslationError(candidate);
        if (!translationError.isEmpty()) throw new IllegalStateException(translationError);
        VerifiedContentSanitizer.sanitize(candidate);
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
        if (error == null) return "network_unknown";
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) message = error.getClass().getSimpleName();
        if (message.startsWith("date_not_ready")) return message;
        if (message.startsWith("http_") || message.startsWith("signature_http_")) return message;
        if (message.contains("payload") || message.contains("schema") || message.contains("signature") || message.contains("signed_") || message.contains("missing") || message.contains("incomplete") || message.contains("integrity") || message.contains("content_type") || message.contains("too_large") || message.contains("translation") || message.contains("language_lane") || message.contains("localized_script") || message.contains("date_in_future") || message.contains("date_invalid")) {
            return "invalid_" + message;
        }
        return "network_" + error.getClass().getSimpleName();
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
        if (baseId.isEmpty()) return service;

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
            applySegmentReplacements(
                    resolvedBaseSegments,
                    service.optJSONObject("segment_replacements"),
                    service.optJSONObject("inline_replacements")
            );
            pruneUnresolvedOrEmptySegments(resolvedBaseSegments);
            JSONArray merged = new JSONArray();
            appendSegments(merged, service.optJSONArray("segments"));
            appendSegments(merged, resolvedBaseSegments);
            resolved.put("segments", merged);
            resolved.remove("segment_replacements");
            resolved.remove("inline_replacements");
            resolved.put("composed_from", baseId);
            return resolved;
        } catch (Exception error) {
            Log.w(TAG, "Could not compose daily service overlay " + service.optString("id"), error);
            return service;
        }
    }

    private static void applySegmentReplacements(JSONArray segments, JSONObject exact, JSONObject inline) {
        if (segments == null) return;
        for (int i = 0; i < segments.length(); i++) {
            Object value = segments.opt(i);
            applyReplacementsToValue(value, exact, inline);
        }
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
                if (value.contains("[") && value.contains("]")) hasUnresolvedMarker = true;
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
            if (!isRenderableService(service) || !category.equals(service.optString("category"))) continue;
            output.putIfAbsent(service.optString("id", "service-" + i), resolveService(service));
        }
    }

    private void collectAll(JSONArray array, Map<String, JSONObject> output) {
        if (array == null) return;
        for (int i = 0; i < array.length(); i++) {
            JSONObject service = array.optJSONObject(i);
            if (isRenderableService(service)) {
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
