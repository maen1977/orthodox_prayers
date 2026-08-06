package com.orthodoxprayers.privateapp.appupdate;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/** Minimal HTTPS client for GitHub Releases with strict redirect and response-size limits. */
public final class AppUpdateClient {
    public interface ProgressCallback { void onProgress(long downloadedBytes, long totalBytes); }

    public static final String LATEST_RELEASE_URL =
            "https://api.github.com/repos/maen1977/orthodox_prayers/releases/latest";
    private static final int CONNECT_TIMEOUT_MS = 15_000;
    private static final int READ_TIMEOUT_MS = 45_000;
    private static final int MAX_REDIRECTS = 6;
    private static final int MAX_METADATA_BYTES = 1_048_576;
    private static final long MAX_APK_BYTES = 250L * 1024L * 1024L;
    private static final String USER_AGENT = "OrthodoxPrayers-AppUpdater/5.2.1";
    private static final Set<String> ALLOWED_HOSTS = new HashSet<>();

    static {
        ALLOWED_HOSTS.add("api.github.com");
        ALLOWED_HOSTS.add("github.com");
        ALLOWED_HOSTS.add("objects.githubusercontent.com");
        ALLOWED_HOSTS.add("release-assets.githubusercontent.com");
        ALLOWED_HOSTS.add("github-releases.githubusercontent.com");
    }

    public AppUpdateRelease fetchLatestRelease() throws IOException {
        JSONObject release = parseObject(readText(LATEST_RELEASE_URL, MAX_METADATA_BYTES), "Invalid GitHub release metadata");
        if (release.optBoolean("draft", false) || release.optBoolean("prerelease", false)) {
            throw new IOException("Latest release is not stable");
        }

        String tagName = release.optString("tag_name", "").trim();
        String tagVersion;
        try {
            tagVersion = AppUpdateRelease.normalizeVersionName(tagName);
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid release tag", error);
        }

        JSONArray assets = release.optJSONArray("assets");
        if (assets == null) throw new IOException("Release has no assets");

        JSONObject defaultApk = null;
        JSONObject manifestAsset = null;
        JSONObject checksumAsset = null;
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.optJSONObject(i);
            if (asset == null || !"uploaded".equals(asset.optString("state", "uploaded"))) continue;
            String name = asset.optString("name", "").trim();
            String lower = name.toLowerCase(Locale.ROOT);
            if ("app-update.json".equals(lower)) manifestAsset = asset;
            if ("church-prayers.apk.sha256".equals(lower)) checksumAsset = asset;
            if ("church-prayers.apk".equals(lower)) defaultApk = asset;
            if (defaultApk == null && lower.endsWith(".apk") && !lower.contains("debug")) defaultApk = asset;
        }

        JSONObject manifest = new JSONObject();
        if (manifestAsset != null) {
            manifest = parseObject(readText(assetUrl(manifestAsset), 65_536), "Invalid app update manifest");
        }

        String manifestVersion = manifest.optString("versionName", tagVersion).trim();
        String versionName;
        try {
            versionName = AppUpdateRelease.normalizeVersionName(manifestVersion);
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid update manifest version", error);
        }
        if (!tagVersion.equals(versionName)) throw new IOException("Release tag and manifest version differ");

        long versionCode = manifest.optLong("versionCode", 0L);
        if (versionCode < 1L) {
            try {
                versionCode = AppUpdateRelease.semanticVersionCode(versionName);
            } catch (IllegalArgumentException error) {
                throw new IOException("Invalid update version code", error);
            }
        }

        String requestedApkName = manifest.optString("apkAsset", "Church-Prayers.apk").trim();
        JSONObject apkAsset = findAsset(assets, requestedApkName);
        if (apkAsset == null) apkAsset = defaultApk;
        if (apkAsset == null) throw new IOException("Release APK is missing");

        String apkUrl = assetUrl(apkAsset);
        long assetSize = apkAsset.optLong("size", 0L);
        long manifestSize = manifest.optLong("sizeBytes", 0L);
        if (manifestSize > 0L && assetSize > 0L && manifestSize != assetSize) {
            throw new IOException("Release APK size differs from manifest");
        }
        long sizeBytes = manifestSize > 0L ? manifestSize : assetSize;
        if (sizeBytes < 1L || sizeBytes > MAX_APK_BYTES) throw new IOException("Invalid release APK size");

        String sha256 = manifest.optString("sha256", "");
        if (sha256.trim().isEmpty()) sha256 = apkAsset.optString("digest", "");
        if (sha256.trim().isEmpty() && checksumAsset != null) {
            sha256 = firstSha256(readText(assetUrl(checksumAsset), 4_096));
        }
        try {
            sha256 = AppUpdateRelease.normalizeSha256(sha256);
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid release checksum", error);
        }
        if (sha256.isEmpty()) throw new IOException("Release checksum is missing");

        return new AppUpdateRelease(
                versionCode,
                versionName,
                manifest.optLong("minimumSupportedVersionCode", 0L),
                manifest.optBoolean("mandatory", false),
                apkUrl,
                sha256,
                sizeBytes,
                release.optString("body", ""),
                tagName
        );
    }

    public void downloadApk(AppUpdateRelease release, File destination, ProgressCallback callback) throws IOException {
        if (release == null) throw new IllegalArgumentException("release");
        File parent = destination.getParentFile();
        if (parent == null || (!parent.isDirectory() && !parent.mkdirs())) {
            throw new IOException("Unable to create update directory");
        }
        File partial = new File(parent, destination.getName() + ".part");
        if (partial.exists() && !partial.delete()) throw new IOException("Unable to replace partial update");

        HttpURLConnection connection = openFollowingRedirects(release.apkUrl);
        long contentLength = connection.getContentLengthLong();
        long expected = release.sizeBytes > 0L ? release.sizeBytes : contentLength;
        if (contentLength > MAX_APK_BYTES || expected > MAX_APK_BYTES) {
            connection.disconnect();
            throw new IOException("APK exceeds size limit");
        }

        long total = 0L;
        byte[] buffer = new byte[64 * 1024];
        try (InputStream input = new BufferedInputStream(connection.getInputStream());
             FileOutputStream output = new FileOutputStream(partial)) {
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > MAX_APK_BYTES || (expected > 0L && total > expected)) {
                    throw new IOException("APK response exceeds declared size");
                }
                output.write(buffer, 0, read);
                if (callback != null) callback.onProgress(total, expected);
            }
            output.getFD().sync();
        } finally {
            connection.disconnect();
        }

        if (total < 1L || (expected > 0L && total != expected)) {
            partial.delete();
            throw new IOException("APK download is incomplete");
        }
        if (destination.exists() && !destination.delete()) {
            partial.delete();
            throw new IOException("Unable to replace cached update");
        }
        if (!partial.renameTo(destination)) {
            partial.delete();
            throw new IOException("Unable to finalize cached update");
        }
    }

    private String readText(String url, int maximumBytes) throws IOException {
        HttpURLConnection connection = openFollowingRedirects(url);
        try (InputStream input = new BufferedInputStream(connection.getInputStream());
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8 * 1024];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > maximumBytes) throw new IOException("Metadata response is too large");
                output.write(buffer, 0, read);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        } finally {
            connection.disconnect();
        }
    }

    private HttpURLConnection openFollowingRedirects(String initialUrl) throws IOException {
        URL current = validateUrl(initialUrl);
        for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
            HttpURLConnection connection = (HttpURLConnection) current.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setRequestProperty("Accept", "application/vnd.github+json, application/octet-stream;q=0.9, */*;q=0.1");
            connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
            connection.setRequestProperty("User-Agent", USER_AGENT);
            int status = connection.getResponseCode();
            if (status >= 200 && status < 300) return connection;
            if (status >= 300 && status < 400) {
                String location = connection.getHeaderField("Location");
                connection.disconnect();
                if (location == null || location.trim().isEmpty()) throw new IOException("Redirect has no location");
                current = validateUrl(new URL(current, location).toString());
                continue;
            }
            connection.disconnect();
            throw new IOException("Update server returned HTTP " + status);
        }
        throw new IOException("Too many update redirects");
    }

    static URL validateUrl(String value) throws IOException {
        try {
            URI uri = URI.create(value == null ? "" : value.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme())) throw new IOException("HTTPS is required");
            String host = uri.getHost();
            if (host == null || !ALLOWED_HOSTS.contains(host.toLowerCase(Locale.ROOT))) {
                throw new IOException("Untrusted update host");
            }
            if (uri.getUserInfo() != null || uri.getPort() != -1) throw new IOException("Unsafe update URL");
            return uri.toURL();
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid update URL", error);
        }
    }


    private static JSONObject parseObject(String text, String message) throws IOException {
        try {
            return new JSONObject(text == null ? "{}" : text);
        } catch (Exception error) {
            throw new IOException(message, error);
        }
    }

    private static JSONObject findAsset(JSONArray assets, String requestedName) {
        if (requestedName == null || requestedName.trim().isEmpty()) return null;
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.optJSONObject(i);
            if (asset != null && requestedName.equals(asset.optString("name", ""))) return asset;
        }
        return null;
    }

    private static String assetUrl(JSONObject asset) throws IOException {
        String value = asset.optString("browser_download_url", "").trim();
        validateUrl(value);
        return value;
    }

    private static String firstSha256(String text) {
        if (text == null) return "";
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("(?i)(?:sha256:)?([0-9a-f]{64})")
                .matcher(text);
        return matcher.find() ? matcher.group(1) : "";
    }
}
