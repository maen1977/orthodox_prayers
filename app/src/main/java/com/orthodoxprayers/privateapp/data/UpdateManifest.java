package com.orthodoxprayers.privateapp.data;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.Locale;
import java.util.regex.Pattern;

/** Parses a verified update manifest and selects the safest payload for the active language. */
public final class UpdateManifest {
    private static final Pattern SHA256 = Pattern.compile("^[0-9a-f]{64}$");
    private static final Pattern SAFE_PATH = Pattern.compile("^data/[A-Za-z0-9._/-]+$");
    private static final String MANIFEST_SUFFIX = "/data/update-manifest.json";

    public static final class Selection {
        public final String dataUrl;
        public final String signatureUrl;
        public final String sha256;
        public final long revision;
        public final int minimumAppVersionCode;
        public final int sizeBytes;

        Selection(
                String dataUrl,
                String signatureUrl,
                String sha256,
                long revision,
                int minimumAppVersionCode,
                int sizeBytes
        ) {
            this.dataUrl = dataUrl;
            this.signatureUrl = signatureUrl;
            this.sha256 = sha256;
            this.revision = revision;
            this.minimumAppVersionCode = minimumAppVersionCode;
            this.sizeBytes = sizeBytes;
        }
    }

    private UpdateManifest() {}

    public static Selection parse(
            byte[] payload,
            String manifestUrl,
            String expectedDate,
            String language
    ) throws Exception {
        JSONObject manifest = new JSONObject(new String(payload, StandardCharsets.UTF_8));
        if (manifest.optInt("manifest_schema_version", 0) != 1) {
            throw new IllegalStateException("manifest_schema_unsupported");
        }
        String manifestDate = safe(manifest.optString("date_iso", ""));
        if (manifestDate.isEmpty()) {
            throw new IllegalStateException("manifest_date_invalid");
        }
        long revision = manifest.optLong("revision", 0L);
        if (revision < 1L) throw new IllegalStateException("manifest_revision_invalid");
        int minimumVersion = manifest.optInt("minimum_app_version_code", 0);
        if (minimumVersion < 1) throw new IllegalStateException("manifest_minimum_version_invalid");
        ManifestSecurityPolicy.validatePublicationWindow(
                manifest.optString("published_at_utc", ""),
                manifest.optString("valid_until_utc", "")
        );

        JSONObject coverage = manifest.optJSONObject("coverage");
        if (coverage != null) {
            validateCoverage(coverage, manifestDate, expectedDate);
        } else if (!safe(expectedDate).equals(manifestDate)) {
            // Legacy one-day manifests remain exact-date only.
            throw new IllegalStateException("manifest_date_mismatch");
        }

        JSONObject selected = null;
        JSONObject languages = manifest.optJSONObject("languages");
        String normalizedLanguage = normalizeLanguage(language);
        if (languages != null && !normalizedLanguage.isEmpty()) {
            selected = languages.optJSONObject(normalizedLanguage);
        }
        if (selected == null) selected = manifest.optJSONObject("calendar");
        if (selected == null) throw new IllegalStateException("manifest_payload_missing");
        validateSelectedCoverage(selected, coverage, expectedDate);

        String path = validatedPath(selected.optString("path", ""));
        String signaturePath = validatedPath(selected.optString("signature_path", ""));
        if (!signaturePath.equals(path + ".sig")) {
            throw new IllegalStateException("manifest_signature_path_mismatch");
        }
        String hash = selected.optString("sha256", "").toLowerCase(Locale.ROOT);
        if (!SHA256.matcher(hash).matches()) {
            throw new IllegalStateException("manifest_hash_invalid");
        }
        int size = selected.optInt("size_bytes", 0);
        if (size < 1 || size > DataContract.MAX_SIGNED_PAYLOAD_BYTES) {
            throw new IllegalStateException("manifest_size_invalid");
        }
        return new Selection(
                resolve(manifestUrl, path),
                resolve(manifestUrl, signaturePath),
                hash,
                revision,
                minimumVersion,
                size
        );
    }


    private static void validateCoverage(
            JSONObject coverage,
            String manifestDate,
            String expectedDate
    ) {
        int schema = coverage.optInt("schema_version", 1);
        int dayCount = coverage.optInt("day_count", 0);
        String policy = coverage.optString("policy", "");
        boolean supported = (schema == 1
                && dayCount == 9
                && "NINE_CONSECUTIVE_DAYS_STARTING_TODAY".equals(policy))
                || (schema == 2
                && dayCount == 9
                && "ROLLING_FUTURE_WINDOW".equals(policy));
        if (!supported) throw new IllegalStateException("manifest_coverage_unsupported");

        String startValue = safe(coverage.optString("start_date", ""));
        String endValue = safe(coverage.optString("end_date", ""));
        if (!safe(manifestDate).equals(startValue)) {
            throw new IllegalStateException("manifest_coverage_start_mismatch");
        }
        try {
            LocalDate start = LocalDate.parse(startValue);
            LocalDate end = LocalDate.parse(endValue);
            LocalDate requested = LocalDate.parse(safe(expectedDate));
            if (!start.plusDays(dayCount - 1L).equals(end)) {
                throw new IllegalStateException("manifest_coverage_end_mismatch");
            }
            if (requested.isBefore(start) || requested.isAfter(end)) {
                throw new IllegalStateException("manifest_date_outside_coverage");
            }
        } catch (IllegalStateException error) {
            throw error;
        } catch (Exception error) {
            throw new IllegalStateException("manifest_coverage_date_invalid");
        }
        if (!"COMPLETE".equals(coverage.optString("status", ""))) {
            throw new IllegalStateException("manifest_coverage_incomplete");
        }
    }

    private static void validateSelectedCoverage(
            JSONObject selected,
            JSONObject manifestCoverage,
            String expectedDate
    ) {
        String selectedStart = safe(selected.optString("coverage_start_date", ""));
        String selectedEnd = safe(selected.optString("coverage_end_date", ""));
        int selectedCount = selected.optInt("coverage_day_count", 0);
        boolean hasAnyCoverageField = !selectedStart.isEmpty() || !selectedEnd.isEmpty() || selectedCount > 0;
        if (!hasAnyCoverageField) return;
        if (selectedStart.isEmpty() || selectedEnd.isEmpty() || selectedCount != 9) {
            throw new IllegalStateException("manifest_payload_coverage_invalid");
        }
        try {
            LocalDate start = LocalDate.parse(selectedStart);
            LocalDate end = LocalDate.parse(selectedEnd);
            LocalDate requested = LocalDate.parse(safe(expectedDate));
            if (!start.plusDays(selectedCount - 1L).equals(end)) {
                throw new IllegalStateException("manifest_payload_coverage_end_mismatch");
            }
            if (requested.isBefore(start) || requested.isAfter(end)) {
                throw new IllegalStateException("manifest_payload_date_outside_coverage");
            }
            if (manifestCoverage != null
                    && (!selectedStart.equals(safe(manifestCoverage.optString("start_date", "")))
                    || !selectedEnd.equals(safe(manifestCoverage.optString("end_date", "")))
                    || selectedCount != manifestCoverage.optInt("day_count", 0))) {
                throw new IllegalStateException("manifest_payload_coverage_mismatch");
            }
        } catch (IllegalStateException error) {
            throw error;
        } catch (Exception error) {
            throw new IllegalStateException("manifest_payload_coverage_date_invalid");
        }
    }

    private static String resolve(String manifestUrl, String path) {
        String configured = safe(manifestUrl);
        int marker = configured.indexOf(MANIFEST_SUFFIX);
        if (marker <= 0 || marker + MANIFEST_SUFFIX.length() != configured.length()) {
            throw new IllegalStateException("manifest_url_invalid");
        }
        return configured.substring(0, marker + 1) + path;
    }

    private static String validatedPath(String value) {
        String path = safe(value);
        if (!SAFE_PATH.matcher(path).matches() || path.contains("\\")) {
            throw new IllegalStateException("manifest_path_unsafe");
        }
        for (String segment : path.split("/")) {
            if ("..".equals(segment) || ".".equals(segment)) {
                throw new IllegalStateException("manifest_path_unsafe");
            }
        }
        return path;
    }

    private static String normalizeLanguage(String language) {
        String value = safe(language);
        if ("ar".equals(value) || "en".equals(value) || "el".equals(value)) return value;
        return "";
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }
}
