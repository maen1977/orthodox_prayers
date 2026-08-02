package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import android.app.Instrumentation;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.recyclerview.widget.RecyclerView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.orthodoxprayers.privateapp.data.DataRepository;

import org.junit.AfterClass;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public final class ReaderSmokeTest {
    @BeforeClass
    public static void disableNetworkForOfflineReaderCoverage() throws Exception {
        runShellCommand("svc wifi disable");
        runShellCommand("svc data disable");
        awaitNoValidatedInternet();
    }

    @AfterClass
    public static void restoreNetworkAfterOfflineReaderCoverage() throws Exception {
        IOException firstFailure = null;
        try {
            runShellCommand("svc wifi enable");
        } catch (IOException exc) {
            firstFailure = exc;
        }
        try {
            runShellCommand("svc data enable");
        } catch (IOException exc) {
            if (firstFailure == null) firstFailure = exc;
        }
        if (firstFailure != null) throw firstFailure;
    }

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
            assertReader(scenario, datedEmbeddedServiceId("next_sunday_full_liturgy"), 200);
            assertReader(scenario, "morning_prayer", 5);
        }
    }

    @Test
    public void manualShowAndHideControlsNeverHidesReaderContent() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> activity.navigate("reader", datedEmbeddedServiceId("next_sunday_full_liturgy")));

            ReaderSnapshot collapsed = awaitReaderReady(scenario, 200, "initial collapsed reader");
            clickText(scenario, "عرض أدوات القراءة", "Reader controls toggle was not found");

            ReaderSnapshot expanded = awaitReaderReady(scenario, 200, "expanded reader controls");
            assertTrue(
                    "Showing controls should use only the available reading area",
                    expanded.height <= collapsed.height
            );
            clickText(scenario, "إخفاء أدوات القراءة", "Expanded controls handle was not found");

            ReaderSnapshot collapsedAgain = awaitReaderReady(scenario, 200, "collapsed reader after hiding controls");
            assertTrue(
                    "Hiding controls should restore the reading area",
                    collapsedAgain.height >= expanded.height
            );
        }
    }

    @Test
    public void currentNextSundayServiceRendersWhenTheSignedPackageIsCurrent() {
        OrthodoxPrayersApp app = ApplicationProvider.getApplicationContext();
        org.junit.Assume.assumeTrue(
                "The bundled signed package is intentionally stale on this test date",
                app.repository().isTodayCurrent()
        );
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            assertReader(scenario, "next_sunday_full_liturgy", 200);
        }
    }

    private static void runShellCommand(String command) throws IOException {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        try (ParcelFileDescriptor descriptor =
                     instrumentation.getUiAutomation().executeShellCommand(command);
             FileInputStream input = new FileInputStream(descriptor.getFileDescriptor())) {
            byte[] buffer = new byte[256];
            while (input.read(buffer) != -1) {
                // Drain output so executeShellCommand completes before the test continues.
            }
        }
    }

    private static void awaitNoValidatedInternet() throws InterruptedException {
        Context context = ApplicationProvider.getApplicationContext();
        ConnectivityManager manager =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        assertNotNull("ConnectivityManager is unavailable", manager);

        for (int attempt = 0; attempt < 40; attempt++) {
            Network network = manager.getActiveNetwork();
            NetworkCapabilities capabilities =
                    network == null ? null : manager.getNetworkCapabilities(network);
            if (capabilities == null
                    || !capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
                return;
            }
            Thread.sleep(250L);
        }
        fail("Reader smoke tests require the emulator to be offline");
    }

    private static String datedEmbeddedServiceId(String serviceId) {
        OrthodoxPrayersApp app = ApplicationProvider.getApplicationContext();
        DataRepository repository = app.repository();
        return DataRepository.datedServiceId(repository.dataDate(), serviceId);
    }

    private static void assertReader(ActivityScenario<MainActivity> scenario, String serviceId, int minimumItems) {
        scenario.onActivity(activity -> activity.navigate("reader", serviceId));
        awaitReaderReady(scenario, minimumItems, "reader for " + serviceId);
    }

    private static ReaderSnapshot awaitReaderReady(
            ActivityScenario<MainActivity> scenario,
            int minimumItems,
            String stage
    ) {
        long deadline = SystemClock.elapsedRealtime() + 12_000L;
        ReaderSnapshot last = ReaderSnapshot.missing();

        while (SystemClock.elapsedRealtime() < deadline) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            AtomicReference<ReaderSnapshot> current = new AtomicReference<>(ReaderSnapshot.missing());
            scenario.onActivity(activity -> {
                RecyclerView reader = findFirst(activity.getWindow().getDecorView(), RecyclerView.class);
                ReaderSnapshot snapshot = ReaderSnapshot.capture(reader);
                current.set(snapshot);
                if (reader != null
                        && snapshot.adapterItems >= minimumItems
                        && snapshot.height > 0
                        && snapshot.childCount == 0) {
                    reader.requestLayout();
                    reader.postInvalidateOnAnimation();
                }
            });
            last = current.get();
            if (last.isReady(minimumItems)) {
                assertReaderSnapshot(last, minimumItems);
                return last;
            }
            SystemClock.sleep(100L);
        }

        fail("Reader did not become ready during " + stage + ": " + last.describe());
        return last;
    }

    private static void assertReaderSnapshot(ReaderSnapshot reader, int minimumItems) {
        assertTrue("Reader RecyclerView was not found", reader.present);
        assertTrue("Reader adapter was not attached", reader.adapterAttached);
        assertTrue("Reader has too few content rows", reader.adapterItems >= minimumItems);
        assertTrue("Reader has no measured height", reader.height > 0);
        assertTrue(
                "Reader reserves too much blank top padding",
                reader.paddingTop < Math.max(32, reader.height / 3)
        );
        assertTrue("Reader has no visible child rows", reader.childCount > 0);
        if (minimumItems >= 100) {
            assertTrue("Long reader content is not scrollable", reader.canScrollForward);
        }
    }

    private static void clickText(
            ActivityScenario<MainActivity> scenario,
            String needle,
            String failureMessage
    ) {
        scenario.onActivity(activity -> {
            TextView toggle = findTextContaining(activity.getWindow().getDecorView(), needle);
            assertNotNull(failureMessage, toggle);
            assertTrue("Reader controls toggle click was not accepted", toggle.performClick());
        });
    }

    private static final class ReaderSnapshot {
        final boolean present;
        final boolean adapterAttached;
        final int adapterItems;
        final int height;
        final int paddingTop;
        final int childCount;
        final boolean canScrollForward;

        private ReaderSnapshot(
                boolean present,
                boolean adapterAttached,
                int adapterItems,
                int height,
                int paddingTop,
                int childCount,
                boolean canScrollForward
        ) {
            this.present = present;
            this.adapterAttached = adapterAttached;
            this.adapterItems = adapterItems;
            this.height = height;
            this.paddingTop = paddingTop;
            this.childCount = childCount;
            this.canScrollForward = canScrollForward;
        }

        static ReaderSnapshot missing() {
            return new ReaderSnapshot(false, false, 0, 0, 0, 0, false);
        }

        static ReaderSnapshot capture(RecyclerView reader) {
            if (reader == null) return missing();
            RecyclerView.Adapter<?> adapter = reader.getAdapter();
            return new ReaderSnapshot(
                    true,
                    adapter != null,
                    adapter == null ? 0 : adapter.getItemCount(),
                    reader.getHeight(),
                    reader.getPaddingTop(),
                    reader.getChildCount(),
                    reader.canScrollVertically(1)
            );
        }

        boolean isReady(int minimumItems) {
            return present
                    && adapterAttached
                    && adapterItems >= minimumItems
                    && height > 0
                    && childCount > 0
                    && (minimumItems < 100 || canScrollForward);
        }

        String describe() {
            return "present=" + present
                    + ", adapterAttached=" + adapterAttached
                    + ", adapterItems=" + adapterItems
                    + ", height=" + height
                    + ", paddingTop=" + paddingTop
                    + ", childCount=" + childCount
                    + ", canScrollForward=" + canScrollForward;
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
