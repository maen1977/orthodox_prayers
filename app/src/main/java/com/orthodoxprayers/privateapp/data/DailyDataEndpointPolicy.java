package com.orthodoxprayers.privateapp.data;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

/** Builds safe, deterministic endpoint candidates for signed daily data. */
public final class DailyDataEndpointPolicy {
    private DailyDataEndpointPolicy() {}

    public static List<String> jsonCandidates(String configuredTodayUrl, String dateIso) {
        LinkedHashSet<String> candidates = new LinkedHashSet<>();
        String configured = configuredTodayUrl == null ? "" : configuredTodayUrl.trim();
        String date = dateIso == null ? "" : dateIso.trim();
        if (configured.isEmpty()) return new ArrayList<>();

        if (!date.isEmpty() && configured.endsWith("/today.json")) {
            candidates.add(configured.substring(0, configured.length() - "today.json".length()) + date + ".json");
        }
        candidates.add(configured);
        return new ArrayList<>(candidates);
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
