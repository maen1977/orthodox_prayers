package com.orthodoxprayers.privateapp;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.orthodoxprayers.privateapp.data.DataRepository;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Runtime proof that a corrupt local generation cannot replace the embedded trusted package. */
@RunWith(AndroidJUnit4.class)
public final class FailureRecoverySmokeTest {
    @Test
    public void corruptCurrentGenerationFallsBackToEmbeddedTrustedData() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        AppPreferences preferences = new AppPreferences(context);
        String language = preferences.effectiveLanguage();
        File lane = new File(new File(context.getFilesDir(), "trusted_daily_data"), language);
        assertTrue(lane.mkdirs() || lane.isDirectory());
        File reference = new File(lane, "current.ref");
        byte[] original = reference.isFile() ? Files.readAllBytes(reference.toPath()) : null;

        File generation = new File(lane, "generation-corrupt-r43");
        assertTrue(generation.mkdirs() || generation.isDirectory());
        Files.write(new File(generation, "today.json").toPath(), "{broken".getBytes(StandardCharsets.UTF_8));
        Files.write(new File(generation, "today.json.sig").toPath(), "bad-signature".getBytes(StandardCharsets.UTF_8));
        Files.write(reference.toPath(), "generation-corrupt-r43\n".getBytes(StandardCharsets.UTF_8));

        try {
            DataRepository recovered = new DataRepository(context, preferences);
            assertTrue("Embedded trusted data should remain displayable", recovered.hasDisplayableData());
            assertNotNull("Core prayer service disappeared after recovery", recovered.findService("morning_prayer"));
            assertTrue("Corrupt local data must not become the trust source",
                    !"stored".equals(recovered.trustSource()) || recovered.hasUsableCurrentData());
        } finally {
            if (original == null) Files.deleteIfExists(reference.toPath());
            else Files.write(reference.toPath(), original);
            Files.deleteIfExists(new File(generation, "today.json").toPath());
            Files.deleteIfExists(new File(generation, "today.json.sig").toPath());
            Files.deleteIfExists(generation.toPath());
        }
    }
}
