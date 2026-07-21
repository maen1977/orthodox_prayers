package com.orthodoxprayers.privateapp.data;

import com.orthodoxprayers.privateapp.model.SearchResult;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class SearchEngine {
    private static final int MAX_RESULTS = 120;
    private SearchEngine() {}

    public static ArrayList<SearchResult> search(DataRepository repository, String query) {
        QueryPlan plan = QueryPlan.create(query);
        ArrayList<SearchResult> empty = new ArrayList<>();
        if (plan.phrase.isEmpty()) return empty;
        Map<String, SearchResult> bestById = new LinkedHashMap<>();

        // Stale signed overlays are never searched as today's liturgical content.
        if (repository.isTodayCurrent()) {
            scanServices(repository.today().optJSONArray("services"), repository, plan, bestById, 12);
            scanReadings(repository.currentReadings(), repository, plan, bestById);
        }
        scanServices(repository.library().optJSONArray("services"), repository, plan, bestById, 0);
        scanIndex(repository.searchDocuments(), repository, plan, bestById);
        scanSources(repository.registeredSources(), repository, plan, bestById);
        scanChurches(repository.registeredChurches(), repository, plan, bestById);
        scanLiveResources(repository.officialLiveResources(), repository, plan, bestById);
        scanLiveResources(repository.officialServiceLinks(), repository, plan, bestById);

        ArrayList<SearchResult> results = new ArrayList<>(bestById.values());
        results.sort(Comparator.comparingInt((SearchResult r) -> r.score).reversed()
                .thenComparing(r -> repository.localized(r.service.optJSONObject("title"), "")));
        if (results.size() > MAX_RESULTS) return new ArrayList<>(results.subList(0, MAX_RESULTS));
        return results;
    }

    private static void scanIndex(JSONArray documents, DataRepository repository, QueryPlan plan,
                                  Map<String, SearchResult> output) {
        if (documents == null) return;
        for (int i = 0; i < documents.length(); i++) {
            JSONObject document = documents.optJSONObject(i);
            if (document == null) continue;
            String searchable = document.optString("search_text", "");
            int match = textScore(searchable, plan);
            if (match <= 0) continue;
            String targetId = document.optString("target_id", "");
            JSONObject service = repository.findService(targetId);
            if (service == null) continue;
            String title = document.optString("title", "");
            String reference = document.optString("reference", "");
            String display = document.optString("display_text", "");
            int score = match + (containsPhrase(title, plan) ? 120 : 0) + (containsPhrase(reference, plan) ? 135 : 0);
            String section = "scripture".equals(document.optString("type"))
                    ? repository.local("الكتاب المقدس", "Scripture", "Ἁγία Γραφή")
                    : repository.local("فهرس النص", "Text index", "Εὐρετήριο κειμένου");
            putBest(output, targetId, new SearchResult(service, snippet(display, plan.phrase), section, score));
        }
    }

    private static void scanServices(JSONArray services, DataRepository repository, QueryPlan plan,
                                     Map<String, SearchResult> output, int freshnessBonus) {
        if (services == null) return;
        for (int i = 0; i < services.length(); i++) {
            JSONObject service = services.optJSONObject(i);
            if (service == null) continue;
            String id = service.optString("id", "service-" + i);
            SearchResult result = scoreService(service, repository, plan, freshnessBonus);
            if (result != null) putBest(output, id, result);
        }
    }

    private static void scanReadings(JSONArray readings, DataRepository repository, QueryPlan plan,
                                     Map<String, SearchResult> output) {
        if (readings == null) return;
        for (int i = 0; i < readings.length(); i++) {
            JSONObject reading = readings.optJSONObject(i);
            if (reading == null) continue;
            String kind = reading.optString("kind", "reading");
            String title = repository.localized(reading.optJSONObject("title"), kind);
            String reference = repository.localized(reading.optJSONObject("reference"), "");
            String body = repository.localized(reading.optJSONObject("body"), "");
            int titleScore = textScore(title, plan);
            int referenceScore = textScore(reference, plan);
            int bodyScore = textScore(body, plan);
            int score = Math.max(titleScore > 0 ? titleScore + 120 : 0,
                    referenceScore > 0 ? referenceScore + 145 : 0);
            score = Math.max(score, bodyScore > 0 ? bodyScore + 55 : 0);
            if (score <= 0) continue;
            JSONObject service = pseudoService("daily-reading-" + kind, "📖", title, reference, body, "");
            putBest(output, service.optString("id"), new SearchResult(service,
                    snippet(reference.isEmpty() ? body : reference + "\n" + body, plan.phrase),
                    repository.local("قراءات اليوم", "Today’s readings", "Σημερινὰ ἀναγνώσματα"), score + 15));
        }
    }

    private static void scanSources(JSONArray sources, DataRepository repository, QueryPlan plan,
                                    Map<String, SearchResult> output) {
        if (sources == null) return;
        for (int i = 0; i < sources.length(); i++) {
            JSONObject source = sources.optJSONObject(i);
            if (source == null) continue;
            String id = source.optString("id", "source-" + i);
            String name = repository.localized(source.optJSONObject("name"), id);
            String usage = repository.localized(source.optJSONObject("used_for"), "");
            String searchable = name + " " + usage + " " + join(source.optJSONArray("categories"))
                    + " " + join(source.optJSONArray("publication_roles"));
            int score = textScore(searchable, plan);
            if (score <= 0) continue;
            JSONObject health = repository.sourceHealthById(id);
            String healthLine = health == null ? "" : repository.local("حالة الرصد: ", "Monitor status: ", "Κατάσταση ἐλέγχου: ")
                    + health.optString("status", "unknown");
            JSONObject service = pseudoService("source:" + id, "🔗", name, usage,
                    usage + (healthLine.isEmpty() ? "" : "\n" + healthLine), source.optString("url", ""));
            putBest(output, service.optString("id"), new SearchResult(service, snippet(usage, plan.phrase),
                    repository.local("مصدر رسمي", "Official source", "Ἐπίσημη πηγή"), score + 70));
        }
    }

    private static void scanChurches(JSONArray churches, DataRepository repository, QueryPlan plan,
                                     Map<String, SearchResult> output) {
        if (churches == null) return;
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null) continue;
            String id = church.optString("id", "church-" + i);
            String name = repository.metadataLocalized(church.optJSONObject("name"), "");
            String city = repository.metadataLocalized(church.optJSONObject("city"), "");
            String searchable = name + " " + city + " كنيسة رعية كاتدرائية دير church parish cathedral monastery";
            int score = textScore(searchable, plan);
            if (score <= 0) continue;
            String summary = city.isEmpty() ? repository.local("كنيسة أرثوذكسية في الأردن", "Orthodox church in Jordan", "Ὀρθόδοξος ναὸς στὴν Ἰορδανία") : city;
            JSONObject service = pseudoService("church:" + id, "⛪", name, summary,
                    repository.local("افتح الصفحة الرسمية لمعرفة بيانات الاتصال والبرنامج الحالي للخدمات.",
                            "Open the official page for contact details and the current service schedule.",
                            "Ἀνοίξτε τὴν ἐπίσημη σελίδα γιὰ στοιχεῖα καὶ τὸ τρέχον πρόγραμμα."),
                    church.optString("url", ""));
            putBest(output, service.optString("id"), new SearchResult(service, summary,
                    repository.local("دليل الكنائس", "Church directory", "Κατάλογος ναῶν"), score + 95));
        }
    }

    private static void scanLiveResources(JSONArray resources, DataRepository repository, QueryPlan plan,
                                          Map<String, SearchResult> output) {
        if (resources == null) return;
        for (int i = 0; i < resources.length(); i++) {
            JSONObject resource = resources.optJSONObject(i);
            if (resource == null) continue;
            String title = repository.localized(resource.optJSONObject("title"), resource.optString("id"));
            int score = textScore(title + " بث مباشر قداس live stream broadcast calendar رزنامة", plan);
            if (score <= 0) continue;
            JSONObject service = pseudoService("resource:" + resource.optString("id", String.valueOf(i)), "▶", title,
                    repository.local("رابط كنسي رسمي", "Official church link", "Ἐπίσημος ἐκκλησιαστικὸς σύνδεσμος"),
                    title, resource.optString("url", ""));
            putBest(output, service.optString("id"), new SearchResult(service, title,
                    repository.local("روابط مباشرة", "Live resources", "Ζωντανοὶ σύνδεσμοι"), score + 90));
        }
    }

    private static SearchResult scoreService(JSONObject service, DataRepository repository, QueryPlan plan, int freshnessBonus) {
        String title = repository.localized(service.optJSONObject("title"), "");
        String summary = repository.localized(service.optJSONObject("summary"), "");
        String notice = repository.localized(service.optJSONObject("notice"), "");
        int bestScore = textScore(title, plan) + 125;
        String bestText = title;
        String section = repository.local("العنوان", "Title", "Τίτλος");

        int summaryScore = textScore(summary, plan) + 75;
        if (summaryScore > bestScore) {
            bestScore = summaryScore;
            bestText = summary;
            section = repository.local("الملخص", "Summary", "Περίληψη");
        }
        int noticeScore = textScore(notice, plan) + 50;
        if (noticeScore > bestScore) {
            bestScore = noticeScore;
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
                int score = textScore(text, plan) + ("section".equals(segment.optString("type")) ? 55 : 35);
                if (score > bestScore) {
                    bestScore = score;
                    bestText = text;
                    section = repository.localized(segment.optJSONObject("title"),
                            repository.local("داخل النص", "Inside text", "Μέσα στὸ κείμενο"));
                }
            }
        }
        if (bestScore <= 125) return null;
        return new SearchResult(service, snippet(bestText, plan.phrase), section, bestScore + freshnessBonus);
    }

    private static JSONObject pseudoService(String id, String icon, String title, String summary, String body, String externalUrl) {
        JSONObject localizedTitle = localized(title);
        JSONObject localizedSummary = localized(summary);
        JSONObject service = new JSONObject();
        try {
            service.put("id", id);
            service.put("category", "discovery");
            service.put("icon", icon);
            service.put("title", localizedTitle);
            service.put("summary", localizedSummary);
            service.put("segments", new JSONArray().put(new JSONObject()
                    .put("speaker", localizedTitle)
                    .put("text", localized(body))));
            if (externalUrl != null && externalUrl.startsWith("https://")) service.put("external_url", externalUrl);
        } catch (Exception ignored) {}
        return service;
    }

    private static JSONObject localized(String value) {
        JSONObject object = new JSONObject();
        try {
            object.put("ar", value == null ? "" : value);
            object.put("en", value == null ? "" : value);
            object.put("el", value == null ? "" : value);
        } catch (Exception ignored) {}
        return object;
    }

    private static void putBest(Map<String, SearchResult> output, String id, SearchResult result) {
        SearchResult existing = output.get(id);
        if (existing == null || result.score > existing.score) output.put(id, result);
    }

    private static int textScore(String text, QueryPlan plan) {
        String haystack = normalize(text);
        if (haystack.isEmpty()) return 0;
        if (haystack.contains(plan.phrase)) return 85 + Math.min(25, plan.phrase.length());
        String[] words = haystack.split(" ");
        int matched = 0;
        int fuzzy = 0;
        for (String token : plan.tokens) {
            boolean exact = haystack.contains(token);
            if (exact) {
                matched++;
                continue;
            }
            if (token.length() >= 4 && containsNearWord(words, token)) {
                matched++;
                fuzzy++;
            }
        }
        if (matched == 0 || matched < Math.max(1, plan.tokens.size() - 1)) return 0;
        return matched * 22 - fuzzy * 5 + (matched == plan.tokens.size() ? 18 : 0);
    }

    private static boolean containsPhrase(String value, QueryPlan plan) {
        return normalize(value).contains(plan.phrase);
    }

    private static boolean containsNearWord(String[] words, String token) {
        for (String word : words) {
            if (Math.abs(word.length() - token.length()) > 1) continue;
            if (editDistanceAtMostOne(word, token)) return true;
        }
        return false;
    }

    private static boolean editDistanceAtMostOne(String left, String right) {
        if (left.equals(right)) return true;
        if (Math.abs(left.length() - right.length()) > 1) return false;
        int i = 0, j = 0, edits = 0;
        while (i < left.length() && j < right.length()) {
            if (left.charAt(i) == right.charAt(j)) {
                i++; j++; continue;
            }
            if (++edits > 1) return false;
            if (left.length() > right.length()) i++;
            else if (right.length() > left.length()) j++;
            else { i++; j++; }
        }
        if (i < left.length() || j < right.length()) edits++;
        return edits <= 1;
    }

    private static String snippet(String text, String normalizedNeedle) {
        if (text == null) return "";
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= 260) return compact;
        String normalized = normalize(compact);
        int index = normalized.indexOf(normalizedNeedle);
        int start = index < 0 ? 0 : Math.max(0, index - 95);
        int end = Math.min(compact.length(), start + 250);
        String value = compact.substring(start, end);
        if (start > 0) value = "…" + value;
        if (end < compact.length()) value += "…";
        return value;
    }

    private static String join(JSONArray array) {
        if (array == null) return "";
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < array.length(); i++) builder.append(' ').append(array.optString(i));
        return builder.toString();
    }

    public static String normalize(String value) {
        if (value == null) return "";
        String normalized = Normalizer.normalize(value, Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "")
                .replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
                .replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
                .replace("ـ", "")
                .replace('٠', '0').replace('١', '1').replace('٢', '2').replace('٣', '3').replace('٤', '4')
                .replace('٥', '5').replace('٦', '6').replace('٧', '7').replace('٨', '8').replace('٩', '9')
                .toLowerCase(Locale.ROOT);
        return normalized.replaceAll("[^\\p{L}\\p{N}:,-]+", " ").replaceAll("\\s+", " ").trim();
    }

    private static final class QueryPlan {
        final String phrase;
        final Set<String> tokens;

        private QueryPlan(String phrase, Set<String> tokens) {
            this.phrase = phrase;
            this.tokens = tokens;
        }

        static QueryPlan create(String raw) {
            String phrase = normalize(raw);
            Set<String> tokens = new LinkedHashSet<>();
            if (!phrase.isEmpty()) tokens.addAll(Arrays.asList(phrase.split(" ")));
            tokens.removeIf(token -> token.length() < 2);
            return new QueryPlan(phrase, tokens);
        }
    }
}
