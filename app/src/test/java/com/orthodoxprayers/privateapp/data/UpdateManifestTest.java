package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import org.junit.Test;

public final class UpdateManifestTest {
    private static final String URL =
            "https://raw.githubusercontent.com/example/app/verified-data/data/update-manifest.json";

    @Test
    public void selectsTheRequestedLanguageLane() throws Exception {
        UpdateManifest.Selection selection = UpdateManifest.parse(
                manifest("data/daily/2026-07-20/ar.json", "data/daily/2026-07-20/ar.json.sig")
                        .getBytes(StandardCharsets.UTF_8),
                URL,
                "2026-07-20",
                "ar"
        );
        assertEquals(
                "https://raw.githubusercontent.com/example/app/verified-data/data/daily/2026-07-20/ar.json",
                selection.dataUrl
        );
        assertEquals(49L, selection.revision);
        assertEquals(50013, selection.minimumAppVersionCode);
    }

    @Test
    public void fallsBackToTheCombinedCalendarWhenLaneIsMissing() throws Exception {
        String payload = "{"
                + "\"manifest_schema_version\":1,"
                + "\"date_iso\":\"2026-07-20\","
                + "\"revision\":4,"
                + "\"minimum_app_version_code\":50013,"
                + "\"calendar\":{"
                + "\"path\":\"data/calendar/today.json\","
                + "\"signature_path\":\"data/calendar/today.json.sig\","
                + "\"sha256\":\"" + "b".repeat(64) + "\","
                + "\"size_bytes\":100},"
                + "\"languages\":{}"
                + "}";
        UpdateManifest.Selection selection = UpdateManifest.parse(
                payload.getBytes(StandardCharsets.UTF_8), URL, "2026-07-20", "el"
        );
        assertEquals(
                "https://raw.githubusercontent.com/example/app/verified-data/data/calendar/today.json",
                selection.dataUrl
        );
    }

    @Test
    public void resolvesPayloadsAgainstTheSignedMirrorManifest() throws Exception {
        String mirror = "https://cdn.jsdelivr.net/gh/example/app@verified-data/data/update-manifest.json";
        UpdateManifest.Selection selection = UpdateManifest.parse(
                manifest("data/daily/2026-07-20/en.json", "data/daily/2026-07-20/en.json.sig")
                        .replace("\"ar\":", "\"en\":")
                        .getBytes(StandardCharsets.UTF_8),
                mirror,
                "2026-07-20",
                "en"
        );
        assertEquals(
                "https://cdn.jsdelivr.net/gh/example/app@verified-data/data/daily/2026-07-20/en.json",
                selection.dataUrl
        );
    }


    @Test
    public void acceptsShortLivedPublicationWindowAndRejectsReplay() throws Exception {
        Instant now = Instant.now().truncatedTo(ChronoUnit.SECONDS);
        String current = manifest("data/daily/2026-07-20/ar.json", "data/daily/2026-07-20/ar.json.sig")
                .replace(
                        "\"minimum_app_version_code\":50013,",
                        "\"published_at_utc\":\"" + now + "\","
                                + "\"valid_until_utc\":\"" + now.plus(48, ChronoUnit.HOURS) + "\","
                                + "\"minimum_app_version_code\":50013,"
                );
        UpdateManifest.parse(current.getBytes(StandardCharsets.UTF_8), URL, "2026-07-20", "ar");

        String expired = manifest("data/daily/2026-07-20/ar.json", "data/daily/2026-07-20/ar.json.sig")
                .replace(
                        "\"minimum_app_version_code\":50013,",
                        "\"published_at_utc\":\"" + now.minus(96, ChronoUnit.HOURS) + "\","
                                + "\"valid_until_utc\":\"" + now.minus(48, ChronoUnit.HOURS) + "\","
                                + "\"minimum_app_version_code\":50013,"
                );
        assertThrows(
                IllegalStateException.class,
                () -> UpdateManifest.parse(
                        expired.getBytes(StandardCharsets.UTF_8), URL, "2026-07-20", "ar"
                )
        );
    }

    @Test
    public void rejectsUnsafeOrMismatchedMetadata() {
        assertThrows(
                IllegalStateException.class,
                () -> UpdateManifest.parse(
                        manifest("data/../secret.json", "data/../secret.json.sig")
                                .getBytes(StandardCharsets.UTF_8),
                        URL,
                        "2026-07-20",
                        "ar"
                )
        );
        assertThrows(
                IllegalStateException.class,
                () -> UpdateManifest.parse(
                        manifest("data/daily/2026-07-20/ar.json", "data/daily/2026-07-20/ar.json.sig")
                                .getBytes(StandardCharsets.UTF_8),
                        URL,
                        "2026-07-21",
                        "ar"
                )
        );
    }

    private static String manifest(String path, String signaturePath) {
        return "{"
                + "\"manifest_schema_version\":1,"
                + "\"date_iso\":\"2026-07-20\","
                + "\"revision\":49,"
                + "\"minimum_app_version_code\":50013,"
                + "\"calendar\":{"
                + "\"path\":\"data/calendar/today.json\","
                + "\"signature_path\":\"data/calendar/today.json.sig\","
                + "\"sha256\":\"" + "a".repeat(64) + "\","
                + "\"size_bytes\":100},"
                + "\"languages\":{" 
                + "\"ar\":{"
                + "\"path\":\"" + path + "\","
                + "\"signature_path\":\"" + signaturePath + "\","
                + "\"sha256\":\"" + "c".repeat(64) + "\","
                + "\"size_bytes\":120}"
                + "}"
                + "}";
    }
}
