package com.orthodoxprayers.privateapp.data;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

/** Builds safe, deterministic endpoint candidates for signed daily data. */
public final class DailyDataEndpointPolicy {
    private static final String CALENDAR_TODAY_SUFFIX = "/data/calendar/today.json";

    private DailyDataEndpointPolicy() {}

    public static List<String> jsonCandidates(String configuredTodayUrl, String dateIso) {
        return jsonCandidates(configuredTodayUrl, dateIso, "");
    }

    /**
     * Prefer the independently signed selected-language lane. The combined calendar
     * endpoints remain last-known-good fallbacks while an individual lane is missing.
     */
    public static List<String> jsonCandidates(String configuredTodayUrl, String dateIso, String language) {
        LinkedHashSet<String> candidates = new LinkedHashSet<>();
        String configured = configuredTodayUrl == null ? "" : configuredTodayUrl.trim();
        String date = dateIso == null ? "" : dateIso.trim();
        String lane = normalizeLanguage(language);
        if (configured.isEmpty()) return new ArrayList<>();

        if (!lane.isEmpty() && configured.endsWith(CALENDAR_TODAY_SUFFIX)) {
            String repositoryRoot = configured.substring(0, configured.length() - CALENDAR_TODAY_SUFFIX.length());
            if (!date.isEmpty()) {
                candidates.add(repositoryRoot + "/data/daily/" + date + "/" + lane + ".json");
            }
            candidates.add(repositoryRoot + "/data/daily/current/" + lane + ".json");
        }
        if (!date.isEmpty() && configured.endsWith("/today.json")) {
            candidates.add(configured.substring(0, configured.length() - "today.json".length()) + date + ".json");
        }
        candidates.add(configured);
        return new ArrayList<>(candidates);
    }

    private static String normalizeLanguage(String language) {
        String value = language == null ? "" : language.trim();
        if ("ar".equals(value) || "en".equals(value) || "el".equals(value)) return value;
        return "";
    }

    public static String signatureUrl(
            String configuredTodayUrl,
            String configuredTodaySignatureUrl,
            String candidateJsonUrl
    ) {
        String configuredJson = configuredTodayUrl == null ? "" : configuredTodayUrl.trim();
        String configuredSignature = configuredTodaySignatureUrl == null ? "" : configuredTodaySignatureUrl.trim();
        String candidate = candidateJsonUrl == null ? "" : candidateJsonUrl.trim();

        if (candidate.equals(configuredJson) && !configuredSignature.isEmpty()) {
            return configuredSignature;
        }
        return candidate + ".sig";
    }
}
