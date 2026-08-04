package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.orthodoxprayers.privateapp.data.CommemorationDisplayPolicy;
import com.orthodoxprayers.privateapp.data.DataRepository;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

/** Verifies the commemoration show-only-when-verified rule in the real UI for every language. */
@RunWith(AndroidJUnit4.class)
public final class DailyPresentationSmokeTest {
    private static final String[] LANGUAGES = {"ar", "en", "el"};

    @Test
    public void emptyCommemorationNeverCreatesAVisibleField() {
        OrthodoxPrayersApp app = ApplicationProvider.getApplicationContext();
        DataRepository data = app.repository();
        String date = findDate(data, false);
        assertFalse("A no-commemoration calendar day is required", date.isEmpty());

        for (String language : LANGUAGES) {
            app.preferences().setLanguage(language);
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> activity.navigate("calendar_day", date));
                List<String> texts = awaitVisibleTexts(scenario);
                String label = data.local(R.string.ui_commemoration_399506fc).trim();
                for (String text : texts) {
                    String normalized = text.trim();
                    assertFalse("Empty commemoration label leaked in " + language,
                            normalized.equals(label) || normalized.equals(label + ":"));
                    assertFalse("Generic Arabic commemoration placeholder leaked", normalized.contains("تذكار اليوم بحسب التقويم"));
                    assertFalse("Generic English commemoration placeholder leaked", normalized.toLowerCase().contains("daily commemoration according"));
                    assertFalse("Generic Greek commemoration placeholder leaked", normalized.contains("μνήμη τῆς ἡμέρας κατὰ"));
                }
            }
        }
        app.preferences().setLanguage("ar");
    }

    @Test
    public void verifiedCommemorationAppearsOnItsCalendarDay() {
        OrthodoxPrayersApp app = ApplicationProvider.getApplicationContext();
        DataRepository data = app.repository();
        String date = findDate(data, true);
        assertFalse("A verified commemoration calendar day is required", date.isEmpty());

        for (String language : LANGUAGES) {
            app.preferences().setLanguage(language);
            JSONObject day = data.calendarDay(date);
            String expected = CommemorationDisplayPolicy.displayText(day, data::localizedValue).trim();
            assertFalse("Verified commemoration text is empty in " + language, expected.isEmpty());
            try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> activity.navigate("calendar_day", date));
                List<String> texts = awaitVisibleTexts(scenario);
                assertTrue("Verified commemoration is missing in " + language, containsText(texts, expected));
            }
        }
        app.preferences().setLanguage("ar");
    }

    private static String findDate(DataRepository data, boolean requireDisplayable) {
        JSONArray days = data.calendarDays(2026);
        for (int i = 0; i < days.length(); i++) {
            JSONObject day = days.optJSONObject(i);
            if (day == null) continue;
            String value = CommemorationDisplayPolicy.displayText(day, data::localizedValue).trim();
            if (requireDisplayable == !value.isEmpty()) {
                return day.optString("date_iso", day.optString("date", ""));
            }
        }
        return "";
    }

    private static List<String> awaitVisibleTexts(ActivityScenario<MainActivity> scenario) {
        long deadline = SystemClock.elapsedRealtime() + 8_000L;
        AtomicReference<List<String>> latest = new AtomicReference<>(new ArrayList<>());
        while (SystemClock.elapsedRealtime() < deadline) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                ArrayList<String> values = new ArrayList<>();
                collect(activity.getWindow().getDecorView(), values);
                latest.set(values);
            });
            if (!latest.get().isEmpty()) return latest.get();
            SystemClock.sleep(100L);
        }
        assertNotNull(latest.get());
        return latest.get();
    }

    private static void collect(View view, List<String> values) {
        if (view.getVisibility() != View.VISIBLE) return;
        if (view instanceof TextView) {
            CharSequence text = ((TextView) view).getText();
            if (text != null && !text.toString().trim().isEmpty()) values.add(text.toString());
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) collect(group.getChildAt(i), values);
        }
    }

    private static boolean containsText(List<String> values, String expected) {
        for (String value : values) if (value.contains(expected)) return true;
        return false;
    }
}
