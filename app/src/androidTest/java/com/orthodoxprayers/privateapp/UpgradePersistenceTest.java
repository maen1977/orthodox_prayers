package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.os.Build;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Set;

/** Two-phase test used by run_android_upgrade_ci.sh around an adb install -r update. */
@RunWith(AndroidJUnit4.class)
public final class UpgradePersistenceTest {
    private static final String PREFS = "orthodox_prayers_prefs";
    private static final String MARKER = "upgrade-sentinel-r43.txt";

    @Test
    public void seedLegacyState() throws Exception {
        assumeTrue("seed".equals(InstrumentationRegistry.getArguments().getString("upgradePhase", "")));
        Context context = ApplicationProvider.getApplicationContext();
        SharedPreferences values = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        assertTrue(values.edit()
                .putString("language", "en")
                .putBoolean("dark_mode", true)
                .putFloat("font_scale", 1.25f)
                .putString("favorites_csv", "morning_prayer,divine_liturgy")
                .remove("favorites_set_v2")
                .putInt("reader_position_morning_prayer", 7)
                .putInt("reader_offset_morning_prayer", -12)
                .putInt("reader_progress_morning_prayer", 42)
                .putString("last_search_query", "mercy")
                .commit());
        Files.write(
                new File(context.getFilesDir(), MARKER).toPath(),
                "preserve-me".getBytes(StandardCharsets.UTF_8)
        );
    }

    @Test
    public void verifyStateAfterUpgrade() throws Exception {
        assumeTrue("verify".equals(InstrumentationRegistry.getArguments().getString("upgradePhase", "")));
        Context context = ApplicationProvider.getApplicationContext();
        AppPreferences preferences = new AppPreferences(context);
        assertEquals("en", preferences.language());
        assertTrue(preferences.darkMode());
        assertEquals(1.25f, preferences.fontScale(), 0.001f);
        Set<String> favorites = preferences.favorites();
        assertTrue(favorites.contains("morning_prayer"));
        assertTrue(favorites.contains("divine_liturgy"));
        assertEquals(7, preferences.readerPosition("morning_prayer"));
        assertEquals(-12, preferences.readerOffset("morning_prayer"));
        assertEquals(42, preferences.readerProgressPercent("morning_prayer"));
        assertEquals("mercy", preferences.lastSearchQuery());
        assertEquals(
                "preserve-me",
                new String(Files.readAllBytes(new File(context.getFilesDir(), MARKER).toPath()), StandardCharsets.UTF_8)
        );

        PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
        long versionCode = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
        assertTrue("The installed update must be R43 or newer", versionCode >= 50200L);
    }
}
