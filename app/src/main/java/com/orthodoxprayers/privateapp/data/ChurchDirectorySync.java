package com.orthodoxprayers.privateapp.data;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Network-boundary checks for official church directory pages.
 *
 * The synchronizer is deliberately conservative. It may update metadata for
 * records already present in the reviewed snapshot and may repair a known
 * official URL when the page exposes the same record. It never creates a new
 * church from an arbitrary HTML anchor and never deletes a record because a
 * source is temporarily unavailable.
 */
public final class ChurchDirectorySync {
    private static final int MAX_RESPONSE_BYTES = 512_000;
    private static final int CONNECT_TIMEOUT_MS = 12_000;
    private static final int READ_TIMEOUT_MS = 18_000;
    private static final Pattern ANCHOR_PATTERN = Pattern.compile(
            "<a\\b[^>]*\\bhref\\s*=\\s*[\\\"']([^\\\"']+)[\\\"'][^>]*>(.*?)</a>",
            Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
    private static final Pattern TAG_PATTERN = Pattern.compile("<[^>]+>", Pattern.DOTALL);
    private static final Pattern WHITESPACE_PATTERN = Pattern.compile("\\s+");

    private ChurchDirectorySync() {}

    public static Result synchronize(JSONObject current) {
        if (current == null) return Result.retryable("directory_snapshot_empty");
        try {
            JSONObject next = new JSONObject(current.toString());
            JSONArray resources = next.optJSONArray("source_directories");
            JSONArray churches = next.optJSONArray("churches");
            if (resources == null || resources.length() == 0) {
                return Result.retryable("directory_sources_empty");
            }
            if (churches == null || churches.length() == 0) {
                return Result.retryable("directory_churches_empty");
            }

            JSONArray observations = new JSONArray();
            int successful = 0;
            int checked = 0;
            int observedRecords = 0;
            int updatedRecords = 0;
            Set<String> observedIds = new HashSet<>();

            for (int i = 0; i < resources.length(); i++) {
                JSONObject resource = resources.optJSONObject(i);
                if (resource == null) continue;
                String sourceId = resource.optString("id", "source-" + i).trim();
                String url = resource.optString("url", "").trim();
                if (!url.startsWith("https://")) continue;
                checked++;

                FetchResult fetch = fetch(url);
                JSONObject observation = new JSONObject()
                        .put("source_id", sourceId)
                        .put("url", url)
                        .put("http_status", fetch.status)
                        .put("available", fetch.available)
                        .put("content_bytes", fetch.body.length)
                        .put("sha256", fetch.digest)
                        .put("checked_at", Instant.now().toString());

                if (fetch.available) {
                    successful++;
                    MatchResult match = observeKnownRecords(churches, sourceId, url, fetch.body);
                    observedRecords += match.observed;
                    updatedRecords += match.updated;
                    observedIds.addAll(match.ids);
                    observation.put("matched_known_records", match.observed)
                            .put("metadata_updates", match.updated)
                            .put("publication_mode", "known_records_only");
                } else {
                    observation.put("publication_mode", "snapshot_preserved")
                            .put("error", fetch.error == null ? "unavailable" : fetch.error);
                }
                observations.put(observation);
            }

            if (checked == 0 || successful == 0) {
                return Result.retryable("official_directory_sources_unavailable");
            }

            JSONObject sync = new JSONObject()
                    .put("checked_at", Instant.now().toString())
                    .put("sources_checked", checked)
                    .put("sources_available", successful)
                    .put("all_sources_available", successful == checked)
                    .put("known_records_observed", observedRecords)
                    .put("metadata_updates", updatedRecords)
                    .put("snapshot_preserved", true)
                    .put("policy", "Only existing records matched to official pages may be refreshed; missing or unavailable sources never delete local data.");
            next.put("source_observations", observations);
            next.put("directory_sync", sync);
            next.put("directory_sync_status", successful == checked ? "verified" : "partially_verified");
            next.put("last_checked_at", sync.optString("checked_at"));
            next.put("last_known_records_observed", observedIds.size());
            return Result.success(next, checked, successful, observedRecords, updatedRecords);
        } catch (Exception error) {
            return Result.retryable("directory_sync_parse_failed");
        }
    }

    private static FetchResult fetch(String address) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(address).openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("Accept", "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5");
            connection.setRequestProperty("Accept-Language", "ar,en;q=0.8");
            connection.setRequestProperty("User-Agent", "OrthodoxPrayers/5.6.4 official-directory-sync");
            int status = connection.getResponseCode();
            InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            byte[] body = stream == null ? new byte[0] : readLimited(stream, MAX_RESPONSE_BYTES);
            boolean available = status >= 200 && status < 400 && body.length > 0;
            return new FetchResult(status, body, sha256(body), available, null);
        } catch (Exception error) {
            return new FetchResult(0, new byte[0], "", false, error.getClass().getSimpleName());
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static MatchResult observeKnownRecords(JSONArray churches, String sourceId, String baseUrl, byte[] body) throws Exception {
        MatchResult result = new MatchResult();
        String html = new String(body, StandardCharsets.UTF_8);
        Matcher matcher = ANCHOR_PATTERN.matcher(html);
        String checkedAt = Instant.now().toString();
        while (matcher.find()) {
            String href = decodeHtml(matcher.group(1)).trim();
            String label = normalizeLabel(matcher.group(2));
            if (label.isEmpty() || href.isEmpty()) continue;
            String absoluteUrl = resolveUrl(baseUrl, href);
            if (!isOfficialSameHost(baseUrl, absoluteUrl)) continue;
            String normalizedHref = normalizeUrl(absoluteUrl);

            JSONObject matched = null;
            int exactLabelMatches = 0;
            for (int i = 0; i < churches.length(); i++) {
                JSONObject church = churches.optJSONObject(i);
                if (church == null || !belongsToSource(church, sourceId)) continue;
                String knownUrl = normalizeUrl(church.optString("url", ""));
                JSONObject names = church.optJSONObject("name");
                String knownArabicName = normalizeLabel(names == null ? "" : names.optString("ar", ""));
                if (!normalizedHref.isEmpty() && normalizedHref.equals(knownUrl)) {
                    matched = church;
                    break;
                }
                if (!knownArabicName.isEmpty() && label.equals(knownArabicName)) {
                    matched = church;
                    exactLabelMatches++;
                }
            }
            if (matched == null || (exactLabelMatches > 1 && !normalizedHref.equals(normalizeUrl(matched.optString("url", ""))))) {
                continue;
            }

            String id = matched.optString("id", "").trim();
            if (id.isEmpty() || result.ids.contains(id)) continue;
            result.ids.add(id);
            result.observed++;
            int before = matched.toString().hashCode();
            matched.put("source_last_seen_at", checkedAt)
                    .put("source_last_seen_id", sourceId)
                    .put("source_last_seen_label_ar", label);
            if (!normalizedHref.isEmpty() && !normalizedHref.equals(normalizeUrl(matched.optString("url", "")))) {
                matched.put("url", absoluteUrl)
                        .put("link_kind", "official_directory_entry");
            }
            if (matched.toString().hashCode() != before) result.updated++;
        }
        return result;
    }

    private static boolean belongsToSource(JSONObject church, String sourceId) {
        JSONArray sourceIds = church.optJSONArray("directory_source_ids");
        if (sourceIds != null) {
            for (int i = 0; i < sourceIds.length(); i++) {
                if (sourceId.equals(sourceIds.optString(i, ""))) return true;
            }
        }
        return sourceId.equals(church.optString("source_id", ""));
    }

    private static String resolveUrl(String baseUrl, String href) {
        try {
            return new URL(new URL(baseUrl), href).toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    private static boolean isOfficialSameHost(String baseUrl, String candidate) {
        try {
            String baseHost = new URL(baseUrl).getHost().toLowerCase(Locale.ROOT);
            String candidateHost = new URL(candidate).getHost().toLowerCase(Locale.ROOT);
            return !baseHost.isEmpty() && baseHost.equals(candidateHost);
        } catch (Exception ignored) {
            return false;
        }
    }

    private static String normalizeUrl(String value) {
        if (value == null || value.trim().isEmpty()) return "";
        try {
            URI uri = new URI(value.trim());
            String host = uri.getHost();
            if (host == null || host.trim().isEmpty()) return "";
            String path = uri.getPath() == null ? "" : URLDecoder.decode(uri.getPath(), StandardCharsets.UTF_8.name());
            path = path.replaceAll("/+", "/");
            while (path.endsWith("/") && path.length() > 1) path = path.substring(0, path.length() - 1);
            return host.toLowerCase(Locale.ROOT) + path.toLowerCase(Locale.ROOT);
        } catch (Exception ignored) {
            return value.trim().toLowerCase(Locale.ROOT).replaceAll("/+$", "");
        }
    }

    private static String normalizeLabel(String value) {
        if (value == null) return "";
        String clean = decodeHtml(value);
        clean = TAG_PATTERN.matcher(clean).replaceAll(" ");
        clean = clean.replace('\u00a0', ' ');
        return WHITESPACE_PATTERN.matcher(clean).replaceAll(" ").trim();
    }

    private static String decodeHtml(String value) {
        if (value == null) return "";
        String decoded = value.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&quot;", "\"")
                .replace("&#39;", "'")
                .replace("&apos;", "'")
                .replace("&lt;", "<")
                .replace("&gt;", ">");
        Matcher decimal = Pattern.compile("&#([0-9]+);").matcher(decoded);
        StringBuffer decimalBuffer = new StringBuffer();
        while (decimal.find()) {
            try {
                decimal.appendReplacement(decimalBuffer, Matcher.quoteReplacement(String.valueOf((char) Integer.parseInt(decimal.group(1)))));
            } catch (Exception ignored) {
                decimal.appendReplacement(decimalBuffer, Matcher.quoteReplacement(decimal.group(0)));
            }
        }
        decimal.appendTail(decimalBuffer);
        Matcher hexadecimal = Pattern.compile("&#x([0-9a-fA-F]+);").matcher(decimalBuffer.toString());
        StringBuffer hexadecimalBuffer = new StringBuffer();
        while (hexadecimal.find()) {
            try {
                hexadecimal.appendReplacement(hexadecimalBuffer, Matcher.quoteReplacement(String.valueOf((char) Integer.parseInt(hexadecimal.group(1), 16))));
            } catch (Exception ignored) {
                hexadecimal.appendReplacement(hexadecimalBuffer, Matcher.quoteReplacement(hexadecimal.group(0)));
            }
        }
        hexadecimal.appendTail(hexadecimalBuffer);
        return hexadecimalBuffer.toString();
    }

    private static byte[] readLimited(InputStream input, int maxBytes) throws Exception {
        try (InputStream stream = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int read;
            while ((read = stream.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) throw new IllegalStateException("directory_response_too_large");
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    private static String sha256(byte[] bytes) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(bytes);
        StringBuilder output = new StringBuilder(hash.length * 2);
        for (byte value : hash) output.append(String.format(Locale.ROOT, "%02x", value));
        return output.toString();
    }

    private static final class FetchResult {
        final int status;
        final byte[] body;
        final String digest;
        final boolean available;
        final String error;

        FetchResult(int status, byte[] body, String digest, boolean available, String error) {
            this.status = status;
            this.body = body;
            this.digest = digest;
            this.available = available;
            this.error = error;
        }
    }

    private static final class MatchResult {
        final Set<String> ids = new HashSet<>();
        int observed;
        int updated;
    }

    public static final class Result {
        public final JSONObject payload;
        public final boolean success;
        public final boolean retryable;
        public final int checked;
        public final int available;
        public final int recordsObserved;
        public final int recordsUpdated;
        public final String message;

        private Result(JSONObject payload, boolean success, boolean retryable, int checked, int available,
                       int recordsObserved, int recordsUpdated, String message) {
            this.payload = payload;
            this.success = success;
            this.retryable = retryable;
            this.checked = checked;
            this.available = available;
            this.recordsObserved = recordsObserved;
            this.recordsUpdated = recordsUpdated;
            this.message = message;
        }

        static Result success(JSONObject payload, int checked, int available, int recordsObserved, int recordsUpdated) {
            return new Result(payload, true, false, checked, available, recordsObserved, recordsUpdated, "verified");
        }

        static Result retryable(String message) {
            return new Result(null, false, true, 0, 0, 0, 0, message);
        }
    }
}
