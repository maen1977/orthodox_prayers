package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.ArrayList;
import java.util.List;

/** Runtime accessibility guard for the low-memory and current Android emulator lanes. */
@RunWith(AndroidJUnit4.class)
public final class AccessibilitySmokeTest {
    private static final int MINIMUM_TOUCH_TARGET_DP = 48;

    @Before
    public void resetPreferences() {
        Context context = ApplicationProvider.getApplicationContext();
        boolean committed = context.getSharedPreferences("orthodox_prayers_prefs", Context.MODE_PRIVATE)
                .edit()
                .clear()
                .putString("language", "ar")
                .putFloat("font_scale", 1.65f)
                .commit();
        assertTrue("Unable to prepare accessibility preferences", committed);
    }

    @Test
    public void homeAndReaderKeepAccessibleTouchTargetsAtLargeText() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            assertScreenHasReadableContent(scenario, "home");
            assertTouchTargets(scenario, "home");

            scenario.onActivity(activity -> activity.navigate("reader", "morning_prayer"));
            settle();
            assertScreenHasReadableContent(scenario, "reader");
            assertTouchTargets(scenario, "reader");
        }
    }

    private static void assertScreenHasReadableContent(
            ActivityScenario<MainActivity> scenario,
            String stage
    ) {
        settle();
        scenario.onActivity(activity -> {
            View decor = activity.getWindow().getDecorView();
            assertNotNull("Missing decor view during " + stage, decor);
            assertTrue("Blank screen width during " + stage, decor.getWidth() > 0);
            assertTrue("Blank screen height during " + stage, decor.getHeight() > 0);
            List<TextView> visibleText = new ArrayList<>();
            collectVisibleText(decor, visibleText);
            assertFalse("No readable text was rendered during " + stage, visibleText.isEmpty());
            for (TextView text : visibleText) {
                assertTrue(
                        "Visible text has no measured height during " + stage + ": " + text.getText(),
                        text.getHeight() > 0
                );
            }
        });
    }

    private static void assertTouchTargets(
            ActivityScenario<MainActivity> scenario,
            String stage
    ) {
        float density = ApplicationProvider.getApplicationContext()
                .getResources()
                .getDisplayMetrics()
                .density;
        int minimumPx = Math.max(1, Math.round(MINIMUM_TOUCH_TARGET_DP * density));
        scenario.onActivity(activity -> {
            List<View> targets = new ArrayList<>();
            collectCriticalTargets(activity.getWindow().getDecorView(), targets);
            assertFalse("No accessibility touch targets found during " + stage, targets.isEmpty());
            for (View target : targets) {
                String label = String.valueOf(target.getContentDescription());
                if (target instanceof Button && (label == null || "null".equals(label))) {
                    label = String.valueOf(((Button) target).getText());
                }
                assertTrue(
                        "Touch target is narrower than 48dp during " + stage + ": " + label
                                + " width=" + target.getWidth() + " required=" + minimumPx,
                        target.getWidth() >= minimumPx
                );
                assertTrue(
                        "Touch target is shorter than 48dp during " + stage + ": " + label
                                + " height=" + target.getHeight() + " required=" + minimumPx,
                        target.getHeight() >= minimumPx
                );
            }
        });
    }

    private static void collectCriticalTargets(View view, List<View> output) {
        if (view == null || !view.isShown()) return;
        CharSequence description = view.getContentDescription();
        boolean labelledClickable = view.isClickable()
                && description != null
                && !description.toString().trim().isEmpty();
        if (labelledClickable || (view instanceof Button && view.isClickable())) {
            output.add(view);
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                collectCriticalTargets(group.getChildAt(i), output);
            }
        }
    }

    private static void collectVisibleText(View view, List<TextView> output) {
        if (view == null || !view.isShown()) return;
        if (view instanceof TextView) {
            TextView text = (TextView) view;
            if (text.getText() != null && !text.getText().toString().trim().isEmpty()) {
                output.add(text);
            }
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                collectVisibleText(group.getChildAt(i), output);
            }
        }
    }

    private static void settle() {
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        SystemClock.sleep(500L);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    }
}
