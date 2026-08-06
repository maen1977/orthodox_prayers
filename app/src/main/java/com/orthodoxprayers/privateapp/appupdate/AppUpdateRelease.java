package com.orthodoxprayers.privateapp.appupdate;

import org.json.JSONObject;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Immutable, serializable metadata for one installable application release. */
public final class AppUpdateRelease {
    private static final Pattern SEMVER = Pattern.compile("^v?(\\d+)\\.(\\d+)\\.(\\d+)$");

    public final long versionCode;
    public final String versionName;
    public final long minimumSupportedVersionCode;
    public final boolean mandatory;
    public final String apkUrl;
    public final String sha256;
    public final long sizeBytes;
    public final String releaseNotes;
    public final String tagName;

    public AppUpdateRelease(
            long versionCode,
            String versionName,
            long minimumSupportedVersionCode,
            boolean mandatory,
            String apkUrl,
            String sha256,
            long sizeBytes,
            String releaseNotes,
            String tagName
    ) {
        if (versionCode < 1L) throw new IllegalArgumentException("versionCode");
        if (versionName == null || versionName.trim().isEmpty()) throw new IllegalArgumentException("versionName");
        if (apkUrl == null || apkUrl.trim().isEmpty()) throw new IllegalArgumentException("apkUrl");
        this.versionCode = versionCode;
        this.versionName = normalizeVersionName(versionName);
        this.minimumSupportedVersionCode = Math.max(0L, minimumSupportedVersionCode);
        this.mandatory = mandatory;
        this.apkUrl = apkUrl.trim();
        this.sha256 = normalizeSha256(sha256);
        this.sizeBytes = Math.max(0L, sizeBytes);
        this.releaseNotes = releaseNotes == null ? "" : releaseNotes.trim();
        this.tagName = tagName == null ? "" : tagName.trim();
    }

    public boolean isNewerThan(long installedVersionCode) {
        return versionCode > installedVersionCode;
    }

    public boolean isMandatoryFor(long installedVersionCode) {
        return mandatory || (minimumSupportedVersionCode > 0L
                && installedVersionCode < minimumSupportedVersionCode);
    }

    public JSONObject toJson() {
        JSONObject object = new JSONObject();
        try {
            object.put("versionCode", versionCode);
            object.put("versionName", versionName);
            object.put("minimumSupportedVersionCode", minimumSupportedVersionCode);
            object.put("mandatory", mandatory);
            object.put("apkUrl", apkUrl);
            object.put("sha256", sha256);
            object.put("sizeBytes", sizeBytes);
            object.put("releaseNotes", releaseNotes);
            object.put("tagName", tagName);
            return object;
        } catch (Exception error) {
            throw new IllegalStateException("Unable to serialize app update metadata", error);
        }
    }

    public static AppUpdateRelease fromJson(String value) {
        try {
            JSONObject object = new JSONObject(value == null ? "{}" : value);
            return new AppUpdateRelease(
                    object.optLong("versionCode", 0L),
                    object.optString("versionName", ""),
                    object.optLong("minimumSupportedVersionCode", 0L),
                    object.optBoolean("mandatory", false),
                    object.optString("apkUrl", ""),
                    object.optString("sha256", ""),
                    object.optLong("sizeBytes", 0L),
                    object.optString("releaseNotes", ""),
                    object.optString("tagName", "")
            );
        } catch (Exception error) {
            throw new IllegalArgumentException("Invalid app update metadata", error);
        }
    }

    /** Maps x.y.z to x*10000+y*100+z, matching this project's Android versionCode convention. */
    public static long semanticVersionCode(String versionName) {
        Matcher matcher = SEMVER.matcher(versionName == null ? "" : versionName.trim());
        if (!matcher.matches()) throw new IllegalArgumentException("Invalid semantic version");
        long major = Long.parseLong(matcher.group(1));
        long minor = Long.parseLong(matcher.group(2));
        long patch = Long.parseLong(matcher.group(3));
        if (major > 200_000L || minor > 99L || patch > 99L) {
            throw new IllegalArgumentException("Semantic version is outside the Android code range");
        }
        return major * 10_000L + minor * 100L + patch;
    }

    public static String normalizeVersionName(String value) {
        String normalized = value == null ? "" : value.trim();
        if (normalized.startsWith("v") || normalized.startsWith("V")) normalized = normalized.substring(1);
        if (!SEMVER.matcher(normalized).matches()) throw new IllegalArgumentException("Invalid version name");
        return normalized;
    }

    public static String normalizeSha256(String value) {
        String normalized = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        if (normalized.startsWith("sha256:")) normalized = normalized.substring("sha256:".length());
        if (normalized.isEmpty()) return "";
        if (!normalized.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("Invalid SHA-256");
        return normalized;
    }
}
