package com.orthodoxprayers.privateapp.data;

import android.content.Context;

import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Builds the current church-day package entirely from immutable assets bundled
 * with the application. No network connection, GitHub workflow, server clock,
 * private key, or remote publication is required.
 *
 * The embedded annual calendar is authoritative for dates, fasting rules,
 * feast rules, reading references and the appointed Liturgy. Exact Scripture
 * text is added only when every requested endpoint exists in the bundled
 * public-domain native corpus. Missing text is left unavailable rather than
 * translated, guessed, or replaced from another language.
 */
public final class LocalDailyContentEngine {
    public static final int WINDOW_DAYS = 9;
    public static final int LOCAL_ENGINE_SCHEMA_VERSION = 3;
    public static final int FIRST_CALENDAR_YEAR = 2026;
    public static final int LAST_CALENDAR_YEAR = 2050;

    private static final String CALENDAR_ASSET_PREFIX = "data/calendar/calendar_";
    private static final String SCRIPTURE_ASSET_PREFIX = "data/scripture/verses_";
    private static final String SCRIPTURE_MANIFEST_PREFIX = "data/scripture/manifest_";
    private static final String DAILY_PROPERS_ASSET = "data/daily_liturgy_propers_overlay.json";
    private static final Pattern CANONICAL_RANGE = Pattern.compile(
            "^([1-3]?[A-Z]+)\\.(\\d+)\\.(\\d+)-(?:([1-3]?[A-Z]+)\\.)?(?:(\\d+)\\.)?(\\d+)$"
    );

    private final Context context;
    private final BibleCorpusRepository fullBible;
    private final Map<Integer, Map<String, JSONObject>> calendarCache = new HashMap<>();
    private final Map<String, ScriptureCorpus> scriptureCache = new HashMap<>();
    private JSONObject dailyPropersOverlay;

    public LocalDailyContentEngine(Context context) {
        this.context = context.getApplicationContext();
        this.fullBible = new BibleCorpusRepository(this.context);
    }

    public JSONObject buildCurrentWindow(LocalDate startDate) throws Exception {
        return buildWindow(startDate, WINDOW_DAYS);
    }

    public synchronized JSONObject buildWindow(LocalDate startDate, int requestedDays) throws Exception {
        if (startDate == null) throw new IllegalArgumentException("local_start_date_missing");
        if (startDate.getYear() < FIRST_CALENDAR_YEAR || startDate.getYear() > LAST_CALENDAR_YEAR) {
            throw new IllegalStateException("local_calendar_year_unsupported:" + startDate.getYear());
        }

        int dayCount = Math.max(1, Math.min(WINDOW_DAYS, requestedDays));
        ArrayList<JSONObject> built = new ArrayList<>();
        for (int offset = 0; offset < dayCount; offset++) {
            LocalDate date = startDate.plusDays(offset);
            if (date.getYear() > LAST_CALENDAR_YEAR) break;
            JSONObject calendarDay = calendarDay(date);
            if (calendarDay == null) {
                if (offset == 0) throw new IllegalStateException("local_calendar_day_missing:" + date);
                break;
            }
            built.add(buildDay(date, calendarDay));
        }
        if (built.isEmpty()) throw new IllegalStateException("local_calendar_window_empty");

        JSONObject root = built.get(0);
        JSONArray future = new JSONArray();
        for (int i = 1; i < built.size(); i++) future.put(built.get(i));
        root.put("weekly_days", future);
        root.put("upcoming", new JSONArray(future.toString()));
        root.put("local_daily_engine_schema", LOCAL_ENGINE_SCHEMA_VERSION);
        root.put("local_daily_window", new JSONObject()
                .put("schema_version", 1)
                .put("policy", "EMBEDDED_CALENDAR_STARTING_TODAY")
                .put("start_date", startDate.toString())
                .put("end_date", startDate.plusDays(built.size() - 1L).toString())
                .put("day_count", built.size())
                .put("network_required", false)
                .put("source", "embedded_calendar_2026_2050"));
        return root;
    }

    private JSONObject buildDay(LocalDate date, JSONObject calendarDay) throws Exception {
        JSONObject result = new JSONObject();
        result.put("schema_version", DataContract.MAX_SUPPORTED_SCHEMA_VERSION);
        result.put("app_title", localized(
                "صلوات الكنيسة الأرثوذكسية",
                "Orthodox Church Prayers",
                "Προσευχὲς τῆς Ὀρθοδόξου Ἐκκλησίας"
        ));
        result.put("date", date.toString());
        result.put("date_iso", date.toString());
        result.put("date_label", dateLabel(date, calendarDay.optJSONObject("civil_weekday")));
        result.put("calendar_label", localized(
                "التقويم الكنسي القديم — الأردن والقدس",
                "Old ecclesiastical calendar — Jordan and Jerusalem",
                "Παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο — Ἰορδανία καὶ Ἱεροσόλυμα"
        ));
        String julianIso = calendarDay.optString("julian_date", "").trim();
        result.put("julian_date", julianIso);
        JSONObject julianLabel = copyObject(calendarDay.optJSONObject("julian_label"));
        if (julianLabel.length() == 0 && !julianIso.isEmpty()) {
            try { julianLabel = oldCalendarDateLabel(LocalDate.parse(julianIso)); }
            catch (Exception ignored) { /* Keep the raw ISO date as the fail-closed UI fallback. */ }
        }
        if (julianLabel.length() > 0) result.put("julian_label", julianLabel);

        JSONObject feast = copyObject(calendarDay.optJSONObject("feast"));
        if (feast.length() == 0) {
            feast = localized(
                    "تذكار اليوم بحسب التقويم الكنسي القديم",
                    "Today’s commemoration according to the old ecclesiastical calendar",
                    "Μνήμη τῆς ἡμέρας κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο"
            );
        }
        result.put("feast", feast);

        JSONObject fast = copyObject(calendarDay.optJSONObject("fast"));
        if (fast.length() == 0) fast = copyObject(calendarDay.optJSONObject("status"));
        if (fast.length() == 0) fast = localized("غير محدد", "Not specified", "Μὴ καθορισμένο");
        result.put("fast", fast);

        JSONObject fasting = copyObject(calendarDay.optJSONObject("fasting"));
        if (fasting.length() == 0) {
            fasting.put("code", "not_specified");
            fasting.put("title", copyObject(fast));
            fasting.put("is_fast", false);
            fasting.put("display_icons", new JSONArray());
        } else if (fasting.optJSONObject("title") == null) {
            fasting.put("title", copyObject(fast));
        }
        result.put("fasting", fasting);
        JSONObject fastDetail = fasting.optJSONObject("detail");
        if (fastDetail != null) result.put("fast_detail", copyObject(fastDetail));

        JSONObject references = copyObject(calendarDay.optJSONObject("reading_references"));
        result.put("reading_references", references);
        JSONArray appointedReferences = calendarDay.optJSONArray("appointed_readings") == null
                ? new JSONArray()
                : new JSONArray(calendarDay.optJSONArray("appointed_readings").toString());
        result.put("appointed_readings", appointedReferences);
        JSONArray readings = buildReadings(references, appointedReferences);
        result.put("readings", readings);

        JSONObject selection = normalizedLiturgySelection(calendarDay.optJSONObject("liturgy_service_selection"));
        result.put("liturgy_service_selection", selection);
        result.put("services", buildServices(date, calendarDay, readings, selection));

        LocalDate nextSunday = nextSundayAfter(date);
        JSONObject nextSundayDay = calendarDay(nextSunday);
        if (nextSundayDay != null) {
            JSONObject nextSundayObject = new JSONObject();
            nextSundayObject.put("date_iso", nextSunday.toString());
            nextSundayObject.put("date_label", dateLabel(nextSunday, nextSundayDay.optJSONObject("civil_weekday")));
            nextSundayObject.put("feast", copyObject(nextSundayDay.optJSONObject("feast")));
            nextSundayObject.put("fast", copyObject(nextSundayDay.optJSONObject("fast")));
            nextSundayObject.put("reading_references", copyObject(nextSundayDay.optJSONObject("reading_references")));
            nextSundayObject.put("liturgy_service_selection", normalizedLiturgySelection(
                    nextSundayDay.optJSONObject("liturgy_service_selection")
            ));
            result.put("next_sunday", nextSundayObject);
        }

        result.put("source_note", localized(
                "تم تجهيز بيانات اليوم محليًا من التقويم والنصوص الأصلية المضمّنة في التطبيق؛ لا يلزم اتصال بالإنترنت.",
                "Today was prepared locally from the calendar and native texts bundled with the app; no internet connection is required.",
                "Τὰ σημερινὰ δεδομένα προετοιμάστηκαν τοπικὰ ἀπὸ τὸ ἐνσωματωμένο ἡμερολόγιο καὶ τὰ πρωτότυπα κείμενα· δὲν ἀπαιτεῖται διαδίκτυο."
        ));
        result.put("translation_notice", localized(
                "لا تُستخدم ترجمة آلية. النص غير الموجود في المصدر الأصلي المضمّن يبقى غير متاح.",
                "Machine translation is not used. Text absent from the bundled native source remains unavailable.",
                "Δὲν χρησιμοποιεῖται μηχανικὴ μετάφραση. Κείμενο ποὺ λείπει ἀπὸ τὴν ἐνσωματωμένη πρωτότυπη πηγὴ παραμένει μὴ διαθέσιμο."
        ));
        result.put("translation_status", "NATIVE_OFFLINE_ASSETS_ONLY");
        result.put("language_content_mode", "STRICT_NATIVE_LANGUAGE_LANES");
        result.put("machine_translation_used", false);
        result.put("automatic_diacritization_used", false);
        result.put("translation_fallback_policy", "SAME_LANGUAGE_ONLY_FAIL_CLOSED");
        result.put("publication", new JSONObject()
                .put("status", "LOCAL_OFFLINE_ENGINE")
                .put("daily_availability", "LOCAL_CALENDAR_READY")
                .put("date_published", date.toString())
                .put("network_required", false)
                .put("fail_closed", true)
                .put("selected_source", "embedded_calendar_2050")
                .put("human_review_required", false));
        result.put("content_metadata", new JSONObject()
                .put("generated_by", "LocalDailyContentEngine")
                .put("engine_schema_version", LOCAL_ENGINE_SCHEMA_VERSION)
                .put("calendar_range", FIRST_CALENDAR_YEAR + "-" + LAST_CALENDAR_YEAR)
                .put("scripture_policy", "FULL_BUNDLED_PUBLIC_DOMAIN_BIBLE_FIRST_THEN_AUDITED_SLICE_FAIL_CLOSED")
                .put("network_required", false));
        result.put("integrity", new JSONObject()
                .put("status", "LOCAL_IMMUTABLE_ASSET_COMPOSITION")
                .put("calendar_source", "app_asset")
                .put("scripture_source", "full_bible_corpus_app_asset")
                .put("machine_translation_used", false)
                .put("automatic_diacritization_used", false));
        result.put("native_text_contract", "embedded_native_assets_v1");
        result.put("daily_update_status", "LOCAL_OFFLINE_READY");
        return result;
    }

    private JSONArray buildReadings(JSONObject references) throws Exception {
        return buildReadings(references, new JSONArray());
    }

    private JSONArray buildReadings(JSONObject references, JSONArray appointedReferences) throws Exception {
        JSONArray readings = new JSONArray();
        if (appointedReferences != null && appointedReferences.length() > 0) {
            for (int i = 0; i < appointedReferences.length(); i++) {
                JSONObject item = appointedReferences.optJSONObject(i);
                if (item == null) continue;
                String kind = item.optString("kind", "appointed").trim();
                if (kind.isEmpty()) kind = "appointed";
                readings.put(buildReading(kind, item));
            }
            return readings;
        }
        readings.put(buildReading("epistle", references.optJSONObject("epistle")));
        readings.put(buildReading("gospel", references.optJSONObject("gospel")));
        JSONObject matins = references.optJSONObject("matins_gospel");
        if (matins != null) readings.put(buildReading("matins_gospel", matins));
        return readings;
    }

    private JSONObject buildReading(String kind, JSONObject referenceData) throws Exception {
        JSONObject reading = new JSONObject();
        reading.put("icon", readingIcon(kind));
        reading.put("kind", kind);
        reading.put("title", readingTitle(kind));

        String canonical = referenceData == null
                ? ""
                : referenceData.optString("canonical_reference", "").trim();
        JSONObject reference = referenceData == null
                ? new JSONObject()
                : copyObject(referenceData.optJSONObject("reference"));
        if (reference.length() == 0) {
            reference = localized(
                    "مرجع القراءة غير متوفر في التقويم المحلي لهذا التاريخ",
                    "The reading reference is not available in the local calendar for this date",
                    "Ἡ παραπομπὴ τοῦ ἀναγνώσματος δὲν εἶναι διαθέσιμη στὸ τοπικὸ ἡμερολόγιο γιὰ αὐτὴν τὴν ἡμέρα"
            );
        }
        reading.put("reference", reference);
        reading.put("canonical_reference", canonical);

        JSONObject body = new JSONObject();
        JSONObject verification = new JSONObject();
        for (String language : new String[]{"ar", "en", "el"}) {
            ResolvedScripture resolved = resolveScripture(language, canonical);
            if (resolved == null || resolved.text.isEmpty()) continue;
            body.put(language, resolved.text);
            verification.put(language, new JSONObject()
                    .put("status", "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS")
                    .put("source_id", resolved.sourceId)
                    .put("source_url", resolved.sourceUrl)
                    .put("canonical_reference", canonical)
                    .put("reference_available", true)
                    .put("text_available", true)
                    .put("text_sha256", sha256(resolved.text.getBytes(StandardCharsets.UTF_8)))
                    .put("ai_translation_used", false)
                    .put("automatic_diacritization_used", false));
        }
        reading.put("body", body);
        reading.put("native_source_verification", verification);
        reading.put("translation_locked", true);
        reading.put("integrity", new JSONObject()
                .put("status", body.length() == 0
                        ? "REFERENCE_ONLY_FAIL_CLOSED"
                        : "EXACT_BUNDLED_NATIVE_SCRIPTURE")
                .put("canonical_reference", canonical)
                .put("ai_translation_used", false)
                .put("automatic_diacritization_used", false));
        return reading;
    }

    private JSONArray buildServices(
            LocalDate date,
            JSONObject calendarDay,
            JSONArray readings,
            JSONObject selection
    ) throws Exception {
        JSONArray services = new JSONArray();
        services.put(buildService("divine_liturgy", "divine_liturgy", "liturgy", "", date, calendarDay, readings, selection, true));
        services.put(buildService("vespers", "vespers", "liturgy", "", date, calendarDay, readings, selection, false));
        services.put(buildService("orthros", "orthros", "liturgy", "", date, calendarDay, readings, selection, false));
        services.put(buildService("morning_prayer", "morning_prayer", "daily", "", date, calendarDay, readings, selection, false));
        services.put(buildService("evening_prayer", "evening_prayer", "daily", "", date, calendarDay, readings, selection, false));
        services.put(buildService("small_compline", "small_compline", "daily", "", date, calendarDay, readings, selection, false));

        LocalDate sunday = nextSundayAfter(date);
        JSONObject sundayDay = calendarDay(sunday);
        JSONObject sundaySelection = sundayDay == null
                ? normalizedLiturgySelection(null)
                : normalizedLiturgySelection(sundayDay.optJSONObject("liturgy_service_selection"));
        JSONArray sundayReadings = sundayDay == null
                ? new JSONArray()
                : buildReadings(
                        sundayDay.optJSONObject("reading_references"),
                        sundayDay.optJSONArray("appointed_readings") == null
                                ? new JSONArray()
                                : sundayDay.optJSONArray("appointed_readings")
                );
        services.put(buildService(
                "next_sunday_full_liturgy",
                "divine_liturgy",
                "liturgy",
                "",
                sunday,
                sundayDay == null ? calendarDay : sundayDay,
                sundayReadings,
                sundaySelection,
                true
        ));
        return services;
    }

    private JSONObject buildService(
            String id,
            String baseId,
            String category,
            String icon,
            LocalDate date,
            JSONObject calendarDay,
            JSONArray readings,
            JSONObject selection,
            boolean liturgy
    ) throws Exception {
        JSONObject service = new JSONObject();
        service.put("id", id);
        if (!liturgy) service.put("extends_service_id", baseId);
        service.put("category", category);
        service.put("icon", icon);
        service.put("title", serviceTitle(id));
        service.put("summary", daySummary(date, calendarDay));
        service.put("translation_status", "native_offline_local_composition");
        service.put("dynamic_date", date.toString());
        service.put("notice", localized(
                "تُركّب معلومات اليوم فوق النص الأصلي الكامل المخزّن داخل التطبيق، دون اتصال بالإنترنت.",
                "Church-day information is composed with the complete native service stored inside the app, without internet access.",
                "Τὰ στοιχεῖα τῆς ἡμέρας συντίθενται μὲ τὴν πλήρη πρωτότυπη ἀκολουθία ποὺ εἶναι ἀποθηκευμένη στὴν ἐφαρμογή, χωρὶς διαδίκτυο."
        ));
        service.put("source_provenance", new JSONObject()
                .put("status", "EMBEDDED_NATIVE_SERVICE_WITH_LOCAL_CALENDAR_OVERLAY")
                .put("calendar_source", "data/calendar/calendar_" + date.getYear() + ".json")
                .put("dynamic_texts_fail_closed", true)
                .put("ai_liturgical_translation_used", false)
                .put("network_required", false));

        JSONArray segments = new JSONArray();
        segments.put(new JSONObject()
                .put("type", "section")
                .put("title", localized("اليوم الكنسي", "Church day", "Ἐκκλησιαστικὴ ἡμέρα")));
        segments.put(new JSONObject()
                .put("type", "text")
                .put("text", dayFacts(date, calendarDay)));
        service.put("segments", segments);

        if (liturgy) {
            String selectedType = selection.optString("service_type", "chrysostom");
            boolean noLiturgy = "no_divine_liturgy".equals(selectedType);
            boolean overrideRequired = "typikon_override_required".equals(selectedType);
            boolean displayable = selection.optBoolean("displayable", false)
                    && !noLiturgy && !overrideRequired;
            String appointedServiceId = selection.optString("service_id", "").trim();
            JSONObject appointedTitle = copyObject(selection.optJSONObject("label"));
            if (appointedTitle.length() > 0) service.put("title", appointedTitle);
            service.put("selected_liturgy_type", selectedType);
            service.put("selected_service_form", selection.optString("service_form", ""));
            service.put("selected_liturgy", copyObject(selection));
            service.put("full_service_complete", displayable);
            service.put("full_service_scope", "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL");
            service.put("strict_core_only", true);
            service.put("adjacent_offices_separate", true);
            service.put("no_unappointed_material", true);
            if (displayable && !appointedServiceId.isEmpty()) {
                service.put("extends_service_id", appointedServiceId);
                service.put("template_id", "library:" + appointedServiceId);
                service.put("publication_status", "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END_LOCAL_OFFLINE");
            } else {
                service.remove("extends_service_id");
                service.remove("template_id");
                service.put("publication_status", noLiturgy
                        ? "NO_DIVINE_LITURGY_APPOINTED"
                        : (overrideRequired
                            ? "BLOCKED_REQUIRES_DATED_OFFICIAL_TYPIKON_OVERRIDE"
                            : "BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION"));
            }
            JSONObject refs = calendarDay.optJSONObject("reading_references");
            service.put("daily_reading_contract", new JSONObject()
                    .put("authority", "embedded_calendar_2026_2050")
                    .put("date_iso", date.toString())
                    .put("epistle_canonical", canonicalReference(refs, "epistle"))
                    .put("gospel_canonical", canonicalReference(refs, "gospel"))
                    .put("strict_core_only", true)
                    .put("no_unappointed_material", true)
                    .put("fail_closed", true)
                    .put("network_required", false));
            JSONObject readingSlots = readingSlotReplacements(readings);
            JSONObject properData = verifiedProperData(date);
            JSONObject properSlots = properData.optJSONObject("replacements");
            mergeSlotReplacements(readingSlots, properSlots);
            JSONObject properProvenance = properData.optJSONObject("provenance");
            if (readingSlots.length() > 0) service.put("slot_replacements", readingSlots);
            if (properProvenance != null && properProvenance.length() > 0) {
                service.put("daily_propers_provenance", properProvenance);
            }
            service.put("liturgy_day_plan", liturgyDayPlan(date, selection, refs));
        }
        return service;
    }

    /** Place the exact native daily readings in their appointed Liturgy slots. */
    private static JSONObject readingSlotReplacements(JSONArray readings) throws Exception {
        JSONObject slots = new JSONObject();
        if (readings == null) return slots;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null) continue;
            String kind = reading.optString("kind", "").trim();
            // The Matins Gospel belongs to Orthros, not to the Divine Liturgy.
            if (!"epistle".equals(kind) && !"gospel".equals(kind)) continue;
            JSONObject body = reading.optJSONObject("body");
            if (body == null || body.length() == 0) continue;
            JSONObject title = reading.optJSONObject("title");
            JSONObject reference = reading.optJSONObject("reference");
            JSONObject replacement = new JSONObject();
            for (String language : new String[]{"ar", "en", "el"}) {
                String text = body.optString(language, "").trim();
                if (text.isEmpty()) continue;
                String name = title == null ? "" : title.optString(language, "").trim();
                String ref = reference == null ? "" : reference.optString(language, "").trim();
                StringBuilder display = new StringBuilder();
                if (!name.isEmpty()) display.append(name);
                if (!ref.isEmpty()) {
                    if (display.length() > 0) display.append(" — ");
                    display.append(ref);
                }
                if (display.length() > 0) display.append("\n\n");
                display.append(text);
                replacement.put(language, display.toString());
            }
            if (replacement.length() > 0) slots.put(kind, replacement);
        }
        return slots;
    }

    private JSONObject verifiedProperData(LocalDate date) throws Exception {
        JSONObject result = new JSONObject()
                .put("replacements", new JSONObject())
                .put("provenance", new JSONObject());
        JSONObject overlay = dailyPropersOverlay();
        JSONObject entries = overlay.optJSONObject("entries");
        JSONObject entry = entries == null ? null : entries.optJSONObject(date.toString());
        if (entry == null) return result;
        JSONObject languages = entry.optJSONObject("languages");
        if (languages == null) return result;
        JSONObject replacements = result.optJSONObject("replacements");
        JSONObject provenance = result.optJSONObject("provenance");
        for (String language : new String[]{"ar", "en", "el"}) {
            JSONObject lane = languages.optJSONObject(language);
            if (lane == null) continue;
            for (String slot : new String[]{"daily_troparion", "daily_kontakion", "communion_hymn"}) {
                JSONObject item = lane.optJSONObject(slot);
                if (item == null) continue;
                String text = item.optString("text", "").trim();
                String declaredHash = item.optString("text_sha256", "").trim();
                if (text.isEmpty() || declaredHash.isEmpty()) continue;
                if (!declaredHash.equals(sha256(text.getBytes(StandardCharsets.UTF_8)))) continue;
                if (!item.optBoolean("permission_confirmed", false)
                        || item.optBoolean("redistribution_review_required", true)
                        || item.optBoolean("machine_translation_used", true)
                        || item.optBoolean("ai_translation_used", true)
                        || item.optBoolean("automatic_diacritization_used", true)
                        || !item.optBoolean("script_isolated", false)) continue;
                String sourceId = item.optString("source_id", "").trim();
                String sourceUrl = item.optString("source_url", "").trim();
                String authorization = item.optString("authorization_reference", "").trim();
                if (sourceId.isEmpty() || sourceUrl.isEmpty() || authorization.isEmpty()) continue;
                JSONObject localized = replacements.optJSONObject(slot);
                if (localized == null) localized = new JSONObject();
                localized.put(language, text);
                replacements.put(slot, localized);
                JSONObject laneProvenance = provenance.optJSONObject(slot);
                if (laneProvenance == null) laneProvenance = new JSONObject();
                laneProvenance.put(language, new JSONObject()
                        .put("text_sha256", declaredHash)
                        .put("source_id", sourceId)
                        .put("source_url", sourceUrl)
                        .put("authorization_reference", authorization)
                        .put("permission_confirmed", true)
                        .put("machine_translation_used", false)
                        .put("script_isolated", true));
                provenance.put(slot, laneProvenance);
            }
        }
        return result;
    }

    private JSONObject dailyPropersOverlay() throws Exception {
        if (dailyPropersOverlay != null) return dailyPropersOverlay;
        try {
            dailyPropersOverlay = new JSONObject(readAssetText(DAILY_PROPERS_ASSET));
        } catch (java.io.IOException missingAsset) {
            // Preserve older builds and fail closed when the optional overlay is absent.
            dailyPropersOverlay = new JSONObject();
        }
        if (!"VERIFIED_PARTIAL_DAILY_LITURGY_PROPERS_OVERLAY".equals(
                dailyPropersOverlay.optString("status", ""))) {
            return new JSONObject();
        }
        return dailyPropersOverlay;
    }

    private static void mergeSlotReplacements(JSONObject target, JSONObject additions) throws Exception {
        if (target == null || additions == null) return;
        for (String slot : new String[]{"daily_troparion", "daily_kontakion", "communion_hymn"}) {
            JSONObject localized = additions.optJSONObject(slot);
            if (localized == null || localized.length() == 0) continue;
            target.put(slot, copyObject(localized));
        }
    }

    private JSONObject liturgyDayPlan(LocalDate date, JSONObject selection, JSONObject refs) throws Exception {
        JSONObject plan = new JSONObject();
        plan.put("date_iso", date.toString());
        plan.put("appointed_liturgy_type", selection.optString("service_type", ""));
        plan.put("appointed_service_id", selection.optString("service_id", ""));
        plan.put("appointed_service_form", selection.optString("service_form", ""));
        plan.put("selection_rule_id", selection.optString("rule_id", ""));
        plan.put("selection_authority", selection.optString("authority", "embedded_calendar_2026_2050"));
        plan.put("displayable", selection.optBoolean("displayable", false));
        plan.put("strict_core_only", true);
        plan.put("scope", "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL");
        plan.put("no_unappointed_material", true);
        plan.put("wrong_liturgy_fallback_allowed", false);
        plan.put("machine_translation_allowed", false);
        plan.put("liturgy_readings", new JSONObject()
                .put("epistle_canonical", canonicalReference(refs, "epistle"))
                .put("gospel_canonical", canonicalReference(refs, "gospel")));
        JSONObject matinsReferenceData = refs == null ? null : refs.optJSONObject("matins_gospel");
        plan.put("orthros_separate", new JSONObject()
                .put("matins_gospel_canonical", canonicalReference(refs, "matins_gospel"))
                .put("matins_gospel_reference", matinsReferenceData == null
                        ? new JSONObject()
                        : copyObject(matinsReferenceData.optJSONObject("reference")))
                .put("belongs_to", "orthros_not_divine_liturgy"));
        plan.put("separate_adjacent_offices", new JSONArray()
                .put("orthros")
                .put("hours")
                .put("proskomide")
                .put("pre_communion_prayers")
                .put("thanksgiving_after_communion"));
        return plan;
    }

    private JSONObject normalizedLiturgySelection(JSONObject original) throws Exception {
        JSONObject selection = copyObject(original);
        if (selection.length() == 0) {
            selection.put("service_type", "chrysostom");
            selection.put("service_form", "morning_divine_liturgy");
            selection.put("rule_id", "ordinary_chrysostom_baseline");
            selection.put("label", localized(
                    "قداس القديس يوحنا الذهبي الفم",
                    "Divine Liturgy of Saint John Chrysostom",
                    "Θεία Λειτουργία τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου"
            ));
            selection.put("displayable", true);
        }
        String serviceType = selection.optString("service_type", "chrysostom").trim();
        String serviceId = selection.optString("service_id", "").trim();
        if (serviceId.isEmpty()) {
            if ("chrysostom".equals(serviceType)) serviceId = "divine_liturgy";
            else if ("basil".equals(serviceType)) serviceId = "divine_liturgy_basil";
            else if ("presanctified".equals(serviceType)) serviceId = "presanctified_liturgy";
            if (!serviceId.isEmpty()) selection.put("service_id", serviceId);
        }
        selection.put("wrong_liturgy_fallback_allowed", false);
        selection.put("full_service_scope", "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL");
        selection.put("strict_core_only", true);
        selection.put("adjacent_offices_separate", true);
        selection.put("no_unappointed_material", true);
        if (selection.optJSONObject("reason") == null) {
            selection.put("reason", localized(
                    "اختيار محلي محسوب من قواعد التقويم الكنسي المضمّنة",
                    "Local selection calculated from the embedded ecclesiastical-calendar rules",
                    "Τοπικὴ ἐπιλογὴ ὑπολογισμένη ἀπὸ τοὺς ἐνσωματωμένους κανόνες τοῦ ἐκκλησιαστικοῦ ἡμερολογίου"
            ));
        }
        if (selection.optJSONObject("service_form_label") == null) {
            selection.put("service_form_label", serviceFormLabel(selection.optString("service_form", "")));
        }
        if (selection.optJSONObject("availability_note") == null) {
            selection.put("availability_note", selection.optBoolean("displayable", true)
                    ? localized(
                            "النص الأصلي الكامل متوفر داخل التطبيق",
                            "The complete native text is available inside the app",
                            "Τὸ πλήρες πρωτότυπο κείμενο εἶναι διαθέσιμο μέσα στὴν ἐφαρμογή"
                    )
                    : localized(
                            "لا يُعرض بديل ليتورجي غير مطابق",
                            "A non-appointed Liturgy is not substituted",
                            "Δὲν ἀντικαθίσταται μὴ προβλεπόμενη Θεία Λειτουργία"
                    ));
        }
        return selection;
    }

    private JSONObject serviceFormLabel(String form) throws Exception {
        if ("vespers_with_divine_liturgy".equals(form)) {
            return localized(
                    "الغروب مع القداس الإلهي",
                    "Vespers with Divine Liturgy",
                    "Ἑσπερινὸς μετὰ Θείας Λειτουργίας"
            );
        }
        if ("presanctified_evening".equals(form) || "lenten_vespers_with_presanctified".equals(form)) {
            return localized(
                    "قداس السابق تقديسه مساءً",
                    "Evening Liturgy of the Presanctified Gifts",
                    "Ἑσπερινὴ Λειτουργία τῶν Προηγιασμένων Δώρων"
            );
        }
        return localized(
                "القداس الإلهي الصباحي",
                "Morning Divine Liturgy",
                "Πρωινὴ Θεία Λειτουργία"
        );
    }

    private JSONObject daySummary(LocalDate date, JSONObject calendarDay) throws Exception {
        JSONObject feast = calendarDay.optJSONObject("feast");
        JSONObject fast = calendarDay.optJSONObject("fast");
        return localized(
                text(feast, "ar", "تذكار اليوم") + " — " + text(fast, "ar", ""),
                text(feast, "en", "Today’s commemoration") + " — " + text(fast, "en", ""),
                text(feast, "el", "Μνήμη τῆς ἡμέρας") + " — " + text(fast, "el", "")
        );
    }

    private JSONObject dayFacts(LocalDate date, JSONObject calendarDay) throws Exception {
        JSONObject label = dateLabel(date, calendarDay.optJSONObject("civil_weekday"));
        JSONObject feast = calendarDay.optJSONObject("feast");
        JSONObject fast = calendarDay.optJSONObject("fast");
        String julian = calendarDay.optString("julian_date", "");
        return localized(
                "التاريخ المدني: " + text(label, "ar", date.toString())
                        + ". التاريخ الكنسي القديم: " + julian
                        + ". التذكار: " + text(feast, "ar", "")
                        + ". حالة الصوم: " + text(fast, "ar", "") + ".",
                "Civil date: " + text(label, "en", date.toString())
                        + ". Old-calendar date: " + julian
                        + ". Commemoration: " + text(feast, "en", "")
                        + ". Fasting: " + text(fast, "en", "") + ".",
                "Πολιτικὴ ἡμερομηνία: " + text(label, "el", date.toString())
                        + ". Παλαιὸ ἡμερολόγιο: " + julian
                        + ". Μνήμη: " + text(feast, "el", "")
                        + ". Νηστεία: " + text(fast, "el", "") + "."
        );
    }

    private JSONObject dateLabel(LocalDate date, JSONObject weekday) throws Exception {
        String arWeekday = text(weekday, "ar", arabicWeekday(date.getDayOfWeek()));
        String enWeekday = text(weekday, "en", date.getDayOfWeek().name());
        String elWeekday = text(weekday, "el", greekWeekday(date.getDayOfWeek()));
        return localized(
                arWeekday + "، " + date.getDayOfMonth() + " " + arabicMonth(date.getMonthValue()) + " " + date.getYear(),
                enWeekday + ", " + englishMonth(date.getMonthValue()) + " " + date.getDayOfMonth() + ", " + date.getYear(),
                elWeekday + ", " + date.getDayOfMonth() + " " + greekMonth(date.getMonthValue()) + " " + date.getYear()
        );
    }

    private JSONObject oldCalendarDateLabel(LocalDate date) throws Exception {
        return localized(
                date.getDayOfMonth() + " " + arabicMonth(date.getMonthValue()) + " " + date.getYear(),
                englishMonth(date.getMonthValue()) + " " + date.getDayOfMonth() + ", " + date.getYear(),
                date.getDayOfMonth() + " " + greekMonth(date.getMonthValue()) + " " + date.getYear()
        );
    }

    private JSONObject serviceTitle(String id) throws Exception {
        switch (id) {
            case "divine_liturgy": return localized("خدمة اليوم — القداس الإلهي", "Today — Divine Liturgy", "Σήμερα — Θεία Λειτουργία");
            case "vespers": return localized("صلاة الغروب — اليوم", "Vespers — today", "Ἑσπερινὸς — σήμερα");
            case "orthros": return localized("صلاة السَحَر — اليوم", "Orthros / Matins — today", "Ὄρθρος — σήμερα");
            case "morning_prayer": return localized("صلاة الصباح — اليوم", "Morning Prayer — today", "Πρωινὴ Προσευχή — σήμερα");
            case "evening_prayer": return localized("صلاة المساء — اليوم", "Evening Prayer — today", "Ἑσπερινὴ Προσευχή — σήμερα");
            case "small_compline": return localized("صلاة النوم الصغرى — اليوم", "Small Compline — today", "Μικρὸν Ἀπόδειπνον — σήμερα");
            case "next_sunday_full_liturgy": return localized("الأحد القادم — القداس الإلهي", "Next Sunday — Divine Liturgy", "Ἡ ἐρχόμενη Κυριακή — Θεία Λειτουργία");
            default: return localized("خدمة اليوم", "Today’s service", "Ἀκολουθία τῆς ἡμέρας");
        }
    }

    private JSONObject readingTitle(String kind) throws Exception {
        if ("gospel".equals(kind)) return localized("الإنجيل", "Gospel", "Εὐαγγέλιον");
        if ("matins_gospel".equals(kind)) return localized(
                "إنجيل الدورة (إنجيل السَحَر)",
                "Matins Gospel (Eothinon)",
                "Ἑωθινὸν Εὐαγγέλιον"
        );
        if ("old_testament".equals(kind)) return localized(
                "قراءة معيّنة من العهد القديم",
                "Appointed Old Testament Reading",
                "Ὁρισμένο παλαιοδιαθηκικὸ ἀνάγνωσμα"
        );
        if ("appointed".equals(kind)) return localized(
                "القراءة المعيّنة لليوم",
                "Appointed Reading",
                "Ὁρισμένο ἀνάγνωσμα τῆς ἡμέρας"
        );
        return localized("الرسالة", "Epistle", "Ἀπόστολος");
    }

    private String readingIcon(String kind) {
        return "gospel".equals(kind) || "matins_gospel".equals(kind) ? "" : "";
    }

    private ResolvedScripture resolveScripture(String language, String canonicalReference) throws Exception {
        if (canonicalReference == null || canonicalReference.trim().isEmpty()) return null;
        String normalizedReference = canonicalReference.trim().toUpperCase(Locale.ROOT);
        try {
            BibleCorpusRepository.ResolvedPassage complete = fullBible.resolve(language, normalizedReference);
            if (complete != null && complete.text != null && !complete.text.trim().isEmpty()) {
                return new ResolvedScripture(complete.text, complete.sourceId, complete.sourceUrl);
            }
        } catch (java.io.IOException ignored) {
            // Source checkouts may omit the generated corpus until the build-time fetch task runs.
            // Keep the legacy audited slices as a fail-closed development fallback only.
        }
        ScriptureCorpus corpus = scriptureCorpus(language);
        if (corpus == null || corpus.verses.isEmpty()) return null;
        boolean hasDeclaredCoverage = !corpus.supportedReferences.isEmpty();
        if (hasDeclaredCoverage && !corpus.supportedReferences.contains(normalizedReference)) return null;

        ArrayList<JSONObject> selected = new ArrayList<>();
        for (String rawPart : normalizedReference.split(";")) {
            String part = rawPart.trim();
            Matcher matcher = CANONICAL_RANGE.matcher(part);
            if (!matcher.matches()) return null;
            String startBook = matcher.group(1);
            int startChapter = Integer.parseInt(matcher.group(2));
            int startVerse = Integer.parseInt(matcher.group(3));
            String endBook = matcher.group(4) == null ? startBook : matcher.group(4);
            int endChapter = matcher.group(5) == null ? startChapter : Integer.parseInt(matcher.group(5));
            int endVerse = Integer.parseInt(matcher.group(6));
            if (!startBook.equals(endBook)) return null;

            String startId = startBook + "." + startChapter + "." + startVerse;
            String endId = endBook + "." + endChapter + "." + endVerse;
            // Legacy moving-window assets did not declare their complete reference
            // coverage, so retain the old endpoint guard for them. The all-calendar
            // fallback manifest is generated and validated reference-by-reference;
            // it may intentionally follow source-edition numbering that omits a
            // verse number (for example Mark 7:16 in the Patriarchal Greek text).
            if (!hasDeclaredCoverage
                    && (!corpus.byId.containsKey(startId) || !corpus.byId.containsKey(endId))) return null;

            ArrayList<JSONObject> segment = new ArrayList<>();
            for (JSONObject verse : corpus.verses) {
                if (!startBook.equals(verse.optString("book_id", ""))) continue;
                int chapter = verse.optInt("chapter", -1);
                int number = verse.optInt("verse", -1);
                if (comparePosition(chapter, number, startChapter, startVerse) < 0) continue;
                if (comparePosition(chapter, number, endChapter, endVerse) > 0) continue;
                segment.add(verse);
            }
            if (segment.isEmpty()) return null;
            selected.addAll(segment);
        }
        if (selected.isEmpty()) return null;

        StringBuilder text = new StringBuilder();
        JSONObject first = selected.get(0);
        for (JSONObject verse : selected) {
            String value = verse.optString("text", "").trim();
            if (value.isEmpty()) return null;
            if (text.length() > 0) text.append('\n');
            text.append(value);
        }
        return new ResolvedScripture(
                text.toString(),
                first.optString("source_id", corpus.sourceId),
                first.optString("source_url", corpus.sourceUrl)
        );
    }

    private ScriptureCorpus scriptureCorpus(String language) throws Exception {
        ScriptureCorpus cached = scriptureCache.get(language);
        if (cached != null) return cached;

        JSONArray array = new JSONArray(readAssetText(SCRIPTURE_ASSET_PREFIX + language + ".json"));
        JSONObject manifest = new JSONObject(readAssetText(SCRIPTURE_MANIFEST_PREFIX + language + ".json"));
        ArrayList<JSONObject> verses = new ArrayList<>();
        LinkedHashMap<String, JSONObject> byId = new LinkedHashMap<>();
        HashSet<String> supportedReferences = new HashSet<>();
        JSONArray declaredReferences = manifest.optJSONArray("supported_canonical_references");
        if (declaredReferences != null) {
            for (int i = 0; i < declaredReferences.length(); i++) {
                String reference = declaredReferences.optString(i, "").trim().toUpperCase(Locale.ROOT);
                if (!reference.isEmpty()) supportedReferences.add(reference);
            }
        }
        for (int i = 0; i < array.length(); i++) {
            JSONObject verse = array.optJSONObject(i);
            if (verse == null) continue;
            String id = verse.optString("id", "").trim();
            if (id.isEmpty()) continue;
            verses.add(verse);
            byId.put(id, verse);
        }
        verses.sort(Comparator
                .comparing((JSONObject item) -> item.optString("book_id", ""))
                .thenComparingInt(item -> item.optInt("chapter", 0))
                .thenComparingInt(item -> item.optInt("verse", 0)));
        ScriptureCorpus corpus = new ScriptureCorpus(
                verses,
                byId,
                supportedReferences,
                manifest.optString("source_id", "embedded_public_domain_native_corpus"),
                manifest.optString("source_url", "")
        );
        scriptureCache.put(language, corpus);
        return corpus;
    }

    private JSONObject calendarDay(LocalDate date) throws Exception {
        Map<String, JSONObject> year = calendarYear(date.getYear());
        return year == null ? null : year.get(date.toString());
    }

    private Map<String, JSONObject> calendarYear(int year) throws Exception {
        Map<String, JSONObject> cached = calendarCache.get(year);
        if (cached != null) return cached;
        if (year < FIRST_CALENDAR_YEAR || year > LAST_CALENDAR_YEAR) return null;

        JSONObject payload = new JSONObject(readAssetText(CALENDAR_ASSET_PREFIX + year + ".json"));
        JSONArray days = payload.optJSONArray("days");
        if (days == null || days.length() == 0) return null;
        JSONObject fastingProfiles = payload.optJSONObject("fasting_profiles");
        LinkedHashMap<String, JSONObject> result = new LinkedHashMap<>();
        for (int i = 0; i < days.length(); i++) {
            JSONObject day = days.optJSONObject(i);
            if (day == null) continue;
            day = resolveFastingProfile(day, fastingProfiles);
            String date = day.optString("date_iso", day.optString("date", "")).trim();
            if (!date.isEmpty()) result.put(date, day);
        }
        calendarCache.put(year, result);
        return result;
    }

    private static JSONObject resolveFastingProfile(JSONObject item, JSONObject profiles) throws Exception {
        if (item == null || profiles == null) return item;
        JSONObject fasting = item.optJSONObject("fasting");
        if (fasting == null) return item;
        String profileId = fasting.optString("profile_id", "").trim();
        if (profileId.isEmpty()) return item;
        JSONObject profile = profiles.optJSONObject(profileId);
        if (profile == null) return item;
        JSONObject resolved = new JSONObject(profile.toString());
        java.util.Iterator<String> keys = fasting.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            if (!"profile_id".equals(key)) resolved.put(key, fasting.get(key));
        }
        JSONObject copy = new JSONObject(item.toString());
        copy.put("fast", resolved.optJSONObject("title"));
        copy.put("status", resolved.optJSONObject("title"));
        copy.put("fasting", resolved);
        return copy;
    }

    private String readAssetText(String path) throws Exception {
        try (InputStream input = context.getAssets().open(path);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16_384];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read > 0) output.write(buffer, 0, read);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static String canonicalReference(JSONObject refs, String kind) {
        JSONObject item = refs == null ? null : refs.optJSONObject(kind);
        return item == null ? "" : item.optString("canonical_reference", "");
    }

    private static int comparePosition(int chapter, int verse, int otherChapter, int otherVerse) {
        int chapterComparison = Integer.compare(chapter, otherChapter);
        return chapterComparison != 0 ? chapterComparison : Integer.compare(verse, otherVerse);
    }

    private static LocalDate nextSundayAfter(LocalDate date) {
        int days = DayOfWeek.SUNDAY.getValue() - date.getDayOfWeek().getValue();
        if (days <= 0) days += 7;
        return date.plusDays(days);
    }

    private static JSONObject localized(String ar, String en, String el) throws Exception {
        return new JSONObject().put("ar", ar).put("en", en).put("el", el);
    }

    private static JSONObject copyObject(JSONObject value) throws Exception {
        return value == null ? new JSONObject() : new JSONObject(value.toString());
    }

    private static void copyIfPresent(JSONObject source, JSONObject target, String key) throws Exception {
        Object value = source.opt(key);
        if (value == null) return;
        if (value instanceof JSONObject) target.put(key, copyObject((JSONObject) value));
        else if (value instanceof JSONArray) target.put(key, new JSONArray(value.toString()));
        else target.put(key, value);
    }

    private static String text(JSONObject localized, String language, String fallback) {
        if (localized == null) return fallback == null ? "" : fallback;
        String value = localized.optString(language, "").trim();
        return value.isEmpty() ? (fallback == null ? "" : fallback) : value;
    }

    private static String sha256(byte[] data) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte value : digest) result.append(String.format(Locale.ROOT, "%02x", value));
        return result.toString();
    }

    private static String arabicWeekday(DayOfWeek day) {
        String[] values = {"الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"};
        return values[day.getValue() - 1];
    }

    private static String greekWeekday(DayOfWeek day) {
        String[] values = {"Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"};
        return values[day.getValue() - 1];
    }

    private static String arabicMonth(int month) {
        String[] values = {"كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"};
        return values[month - 1];
    }

    private static String englishMonth(int month) {
        String[] values = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"};
        return values[month - 1];
    }

    private static String greekMonth(int month) {
        String[] values = {"Ἰανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Ἀπριλίου", "Μαΐου", "Ἰουνίου", "Ἰουλίου", "Αὐγούστου", "Σεπτεμβρίου", "Ὀκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"};
        return values[month - 1];
    }

    private static final class ScriptureCorpus {
        final List<JSONObject> verses;
        final Map<String, JSONObject> byId;
        final Set<String> supportedReferences;
        final String sourceId;
        final String sourceUrl;

        ScriptureCorpus(
                List<JSONObject> verses,
                Map<String, JSONObject> byId,
                Set<String> supportedReferences,
                String sourceId,
                String sourceUrl
        ) {
            this.verses = verses;
            this.byId = byId;
            this.supportedReferences = supportedReferences;
            this.sourceId = sourceId;
            this.sourceUrl = sourceUrl;
        }
    }

    private static final class ResolvedScripture {
        final String text;
        final String sourceId;
        final String sourceUrl;

        ResolvedScripture(String text, String sourceId, String sourceUrl) {
            this.text = text;
            this.sourceId = sourceId;
            this.sourceUrl = sourceUrl;
        }
    }
}
