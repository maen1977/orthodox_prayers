package com.orthodoxprayers.privateapp.appupdate;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class AppUpdateReleaseTest {
    private static final String SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    @Test
    public void semanticVersionCodeMatchesProjectConvention() {
        assertEquals(50201L, AppUpdateRelease.semanticVersionCode("5.2.1"));
        assertEquals("5.2.1", AppUpdateRelease.normalizeVersionName("v5.2.1"));
    }

    @Test
    public void roundTripsReleaseMetadata() {
        AppUpdateRelease release = new AppUpdateRelease(
                50201L, "5.2.1", 50200L, false,
                "https://github.com/example/app.apk", SHA, 1234L,
                "Notes", "v5.2.1"
        );
        AppUpdateRelease restored = AppUpdateRelease.fromJson(release.toJson().toString());
        assertEquals(50201L, restored.versionCode);
        assertEquals("5.2.1", restored.versionName);
        assertEquals(SHA, restored.sha256);
        assertTrue(restored.isNewerThan(50200L));
        assertFalse(restored.isMandatoryFor(50200L));
        assertTrue(restored.isMandatoryFor(50199L));
    }
}
