package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.app.Instrumentation;
import android.content.Context;
import android.graphics.Bitmap;

import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

@RunWith(AndroidJUnit4.class)
public final class StoreScreenshotTest {
    private static final String[] LANGUAGES = {"ar", "en", "el"};

    @Test
    public void generateRealStoreScreenshotsForAllSupportedLanguages() throws Exception {
        for (String language : LANGUAGES) {
            configureLanguage(language);
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                settle();
                capture(language, "01-home.png");
                scenario.onActivity(activity -> activity.navigate("readings", null));
                settle();
                capture(language, "02-readings.png");
            }
        }
    }

    private static void configureLanguage(String language) {
        Context context = ApplicationProvider.getApplicationContext();
        boolean committed = context.getSharedPreferences("orthodox_prayers_prefs", Context.MODE_PRIVATE)
                .edit()
                .clear()
                .putString("language", language)
                .putBoolean("offline_language_ar", true)
                .putBoolean("offline_language_en", true)
                .putBoolean("offline_language_el", true)
                .commit();
        assertTrue("Unable to prepare screenshot locale " + language, committed);
    }

    private static void settle() throws InterruptedException {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        instrumentation.waitForIdleSync();
        Thread.sleep(800L);
        instrumentation.waitForIdleSync();
    }

    private static void capture(String language, String fileName) throws IOException {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Bitmap bitmap = instrumentation.getUiAutomation().takeScreenshot();
        assertNotNull("The emulator returned no screenshot", bitmap);
        Context context = ApplicationProvider.getApplicationContext();
        File root = new File(context.getExternalFilesDir(null), "store-screenshots/" + language);
        assertTrue("Unable to create screenshot directory", root.isDirectory() || root.mkdirs());
        File output = new File(root, fileName);
        try (FileOutputStream stream = new FileOutputStream(output)) {
            assertTrue("Unable to encode screenshot", bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream));
        } finally {
            bitmap.recycle();
        }
        assertTrue("Screenshot was not written: " + output, output.isFile() && output.length() > 10_000L);
    }
}
