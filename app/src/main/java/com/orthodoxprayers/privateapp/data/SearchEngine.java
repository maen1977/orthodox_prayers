package com.orthodoxprayers.privateapp.data;

import com.orthodoxprayers.privateapp.model.SearchResult;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

public final class SearchEngine {
    private SearchEngine() {}

    public static ArrayList<SearchResult> search(DataRepository repository, String query) {
        String needle = normalize(query);
        ArrayList<SearchResult> empty = new ArrayList<>();
        if (needle.isEmpty()) return empty;
        Map<String, SearchResult> bestById = new LinkedHashMap<>();
        scan(repository.today().optJSONArray("services"), repository, needle, bestById);
        scan(repository.library().optJSONArray("services"), repository, needle, bestById);
        scanIndex(repository.searchDocuments(), repository, needle, bestById);
        ArrayList<SearchResult> results = new ArrayList<>(bestById.values());
        results.sort(Comparator.comparingInt((SearchResult r) -> r.score).reversed()
                .thenComparing(r -> repository.localized(r.service.optJSONObject("title"), "")));
        return results;
    }

    private static void scanIndex(JSONArray documents, DataRepository repository, String needle, Map<String, SearchResult> output) {
        if (documents == null) return;
        for (int i = 0; i < documents.length(); i++) {
            JSONObject document = documents.optJSONObject(i);
            if (document == null) continue;
            String searchable = document.optString("search_text", "");
            if (!searchable.contains(needle)) continue;
            String targetId = document.optString("target_id", "");
            JSONObject service = repository.findService(targetId);
            if (service == null) continue;
            String title = document.optString("title", "");
            String reference = document.optString("reference", "");
            String display = document.optString("display_text", "");
            int score = normalize(title).contains(needle) || normalize(reference).contains(needle) ? 130 : 70;
            String section = "scripture".equals(document.optString("type"))
                    ? repository.local("الكتاب المقدس", "Scripture", "Ἁγία Γραφή")
                    : repository.local("فهرس النص", "Text index", "Εὐρετήριο κειμένου");
            SearchResult result = new SearchResult(service, snippet(display, needle), section, score);
            SearchResult existing = output.get(targetId);
            if (existing == null || result.score > existing.score) output.put(targetId, result);
        }
    }

    private static void scan(JSONArray services, DataRepository repository, String needle, Map<String, SearchResult> output) {
        if (services == null) return;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service == null) continue;
            String id = service.optString("id", "service-" + i);
            SearchResult result = score(service, repository, needle);
            if (result == null) continue;
            SearchResult existing = output.get(id);
            if (existing == null || result.score > existing.score) output.put(id, result);
        }
    }

    private static SearchResult score(JSONObject service, DataRepository repository, String needle) {
        String title = repository.localized(service.optJSONObject("title"), "");
        String summary = repository.localized(service.optJSONObject("summary"), "");
        String notice = repository.localized(service.optJSONObject("notice"), "");
        int bestScore = 0;
        String bestText = "";
        String section = "";

        if (normalize(title).contains(needle)) {
            bestScore = 120;
            bestText = title;
            section = repository.local("العنوان", "Title", "Τίτλος");
        }
        if (normalize(summary).contains(needle) && bestScore < 80) {
            bestScore = 80;
            bestText = summary;
            section = repository.local("الملخص", "Summary", "Περίληψη");
        }
        if (normalize(notice).contains(needle) && bestScore < 60) {
            bestScore = 60;
            bestText = notice;
            section = repository.local("الملاحظة", "Notice", "Σημείωση");
        }

        JSONArray segments = service.optJSONArray("segments");
        if (segments != null) {
            for (int i = 0; i < segments.length(); i++) {
                JSONObject segment = segments.optJSONObject(i);
                if (segment == null) continue;
                String text = repository.localized(segment.optJSONObject("text"), "");
                if (text.isEmpty()) text = repository.localized(segment.optJSONObject("title"), "");
                if (!normalize(text).contains(needle)) continue;
                int score = 35;
                if ("section".equals(segment.optString("type"))) score = 50;
                if (score > bestScore) {
                    bestScore = score;
                    bestText = text;
                    section = repository.localized(segment.optJSONObject("title"), repository.local("داخل النص", "Inside text", "Μέσα στο κείμενο"));
                }
            }
        }
        if (bestScore == 0) return null;
        return new SearchResult(service, snippet(bestText, needle), section, bestScore);
    }

    private static String snippet(String text, String normalizedNeedle) {
        if (text == null) return "";
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= 240) return compact;
        String normalized = normalize(compact);
        int index = normalized.indexOf(normalizedNeedle);
        int start = index < 0 ? 0 : Math.max(0, index - 90);
        int end = Math.min(compact.length(), start + 230);
        if (start > 0) compact = "…" + compact.substring(start, end);
        else compact = compact.substring(0, end);
        if (end < text.length()) compact += "…";
        return compact;
    }

    public static String normalize(String value) {
        if (value == null) return "";
        String normalized = Normalizer.normalize(value, Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "")
                .replace('أ', 'ا')
                .replace('إ', 'ا')
                .replace('آ', 'ا')
                .replace('ى', 'ي')
                .replace('ؤ', 'و')
                .replace('ئ', 'ي')
                .replace("ـ", "")
                .toLowerCase(Locale.ROOT);
        return normalized.replaceAll("\\s+", " ").trim();
    }
}
