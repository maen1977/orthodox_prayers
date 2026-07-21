package com.orthodoxprayers.privateapp.data;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
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
        if (!safe(expectedDate).equals(manifest.optString("date_iso", ""))) {
            throw new IllegalStateException("manifest_date_mismatch");
        }
        long revision = manifest.optLong("revision", 0L);
        if (revision < 1L) throw new IllegalStateException("manifest_revision_invalid");
        int minimumVersion = manifest.optInt("minimum_app_version_code", 0);
        if (minimumVersion < 1) throw new IllegalStateException("manifest_minimum_version_invalid");

        JSONObject selected = null;
        JSONObject languages = manifest.optJSONObject("languages");
        String normalizedLanguage = normalizeLanguage(language);
        if (languages != null && !normalizedLanguage.isEmpty()) {
            selected = languages.optJSONObject(normalizedLanguage);
        }
        if (selected == null) selected = manifest.optJSONObject("calendar");
        if (selected == null) throw new IllegalStateException("manifest_payload_missing");

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
        if (size < 1 || size > 2_000_000) {
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
