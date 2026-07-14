package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.recyclerview.widget.RecyclerView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public final class ReaderSmokeTest {
    @Before
    public void resetReaderState() {
        Context context = ApplicationProvider.getApplicationContext();
        context.getSharedPreferences("orthodox_prayers_prefs", Context.MODE_PRIVATE)
                .edit()
                .clear()
                .commit();
    }

    @Test
    public void prayersAndLiturgiesRenderScrollableContentWithoutBlankViewport() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            assertReader(scenario, "divine_liturgy", 200);
            assertReader(scenario, "next_sunday_full_liturgy", 200);
            assertReader(scenario, "morning_prayer", 5);
        }
    }

    @Test
    public void collapsingAndRestoringControlsNeverHidesReaderContent() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> activity.navigate("reader", "next_sunday_full_liturgy"));
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();

            final int[] initialHeight = new int[1];
            scenario.onActivity(activity -> {
                RecyclerView reader = findFirst(activity.getWindow().getDecorView(), RecyclerView.class);
                assertReaderIsVisible(reader, 200);
                initialHeight[0] = reader.getHeight();
                TextView toggle = findTextContaining(activity.getWindow().getDecorView(), "إخفاء العنوان");
                assertNotNull("Reader controls toggle was not found", toggle);
                toggle.performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();

            scenario.onActivity(activity -> {
                RecyclerView reader = findFirst(activity.getWindow().getDecorView(), RecyclerView.class);
                assertReaderIsVisible(reader, 200);
                assertTrue("Collapsing controls should not reduce the reading area", reader.getHeight() >= initialHeight[0]);
                TextView toggle = findTextContaining(activity.getWindow().getDecorView(), "إظهار عنوان");
                assertNotNull("Collapsed controls handle was not found", toggle);
                toggle.performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();

            scenario.onActivity(activity -> {
                RecyclerView reader = findFirst(activity.getWindow().getDecorView(), RecyclerView.class);
                assertReaderIsVisible(reader, 200);
            });
        }
    }

    private static void assertReader(ActivityScenario<MainActivity> scenario, String serviceId, int minimumItems) {
        scenario.onActivity(activity -> activity.navigate("reader", serviceId));
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        scenario.onActivity(activity -> {
            RecyclerView reader = findFirst(activity.getWindow().getDecorView(), RecyclerView.class);
            assertReaderIsVisible(reader, minimumItems);
        });
    }

    private static void assertReaderIsVisible(RecyclerView reader, int minimumItems) {
        assertNotNull("Reader RecyclerView was not found", reader);
        assertNotNull("Reader adapter was not attached", reader.getAdapter());
        assertTrue("Reader has too few content rows", reader.getAdapter().getItemCount() >= minimumItems);
        assertTrue("Reader has no measured height", reader.getHeight() > 0);
        assertTrue("Reader reserves too much blank top padding", reader.getPaddingTop() < Math.max(32, reader.getHeight() / 3));
        assertTrue("Reader has no visible child rows", reader.getChildCount() > 0);
        if (minimumItems >= 100) {
            assertTrue("Long reader content is not scrollable", reader.canScrollVertically(1));
        }
    }

    private static TextView findTextContaining(View root, String needle) {
        if (root instanceof TextView) {
            CharSequence text = ((TextView) root).getText();
            if (text != null && text.toString().contains(needle)) return (TextView) root;
        }
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int index = 0; index < group.getChildCount(); index++) {
                TextView match = findTextContaining(group.getChildAt(index), needle);
                if (match != null) return match;
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static <T extends View> T findFirst(View root, Class<T> type) {
        if (type.isInstance(root)) return (T) root;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int index = 0; index < group.getChildCount(); index++) {
                T match = findFirst(group.getChildAt(index), type);
                if (match != null) return match;
            }
        }
        return null;
    }
}
