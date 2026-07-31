package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.fail;

import java.io.File;
import java.nio.file.Files;

import org.junit.Test;

public final class DailyDataStoreTest {
    private static final byte[] SIG = "signature".getBytes();

    @Test
    public void failureAfterGenerationSyncLeavesReferencesUntouched() throws Exception {
        File root = Files.createTempDirectory("daily-store-test").toFile();
        DailyDataStore stable = new DailyDataStore(root);
        stable.saveVerified("first".getBytes(), SIG);

        DailyDataStore failing = new DailyDataStore(root, new DailyDataStore.FaultInjector() {
            @Override public void afterGenerationSynced() throws Exception { throw new Exception("injected_generation_failure"); }
            @Override public void afterBackupCommitted() {}
        });
        try {
            failing.saveVerified("second".getBytes(), SIG);
            fail("Expected injected failure");
        } catch (Exception expected) {
            // Expected.
        }

        assertArrayEquals("first".getBytes(), stable.readCurrent().json);
        assertNull(stable.readBackup());
    }

    @Test
    public void failureAfterBackupCommitRestoresPreviousBackupAndCurrent() throws Exception {
        File root = Files.createTempDirectory("daily-store-test").toFile();
        DailyDataStore stable = new DailyDataStore(root);
        stable.saveVerified("first".getBytes(), SIG);

        DailyDataStore failing = new DailyDataStore(root, new DailyDataStore.FaultInjector() {
            @Override public void afterGenerationSynced() {}
            @Override public void afterBackupCommitted() throws Exception { throw new Exception("injected_backup_failure"); }
        });
        try {
            failing.saveVerified("second".getBytes(), SIG);
            fail("Expected injected failure");
        } catch (Exception expected) {
            // Expected.
        }

        assertArrayEquals("first".getBytes(), stable.readCurrent().json);
        assertNull(stable.readBackup());

        stable.saveVerified("second".getBytes(), SIG);
        assertArrayEquals("second".getBytes(), stable.readCurrent().json);
        assertArrayEquals("first".getBytes(), stable.readBackup().json);
    }
    @Test
    public void acceptsSignedPayloadAboveLegacySixMegabyteLimit() throws Exception {
        File root = Files.createTempDirectory("daily-store-large-test").toFile();
        DailyDataStore store = new DailyDataStore(root);
        byte[] payload = new byte[6_000_001];
        payload[0] = '{';
        payload[payload.length - 1] = '}';

        store.saveVerified(payload, SIG);

        assertArrayEquals(payload, store.readCurrent().json);
    }

    @Test
    public void rejectsPayloadAboveSharedTwelveMegabyteLimit() throws Exception {
        File root = Files.createTempDirectory("daily-store-oversize-test").toFile();
        DailyDataStore store = new DailyDataStore(root);
        try {
            store.saveVerified(new byte[DataContract.MAX_SIGNED_PAYLOAD_BYTES + 1], SIG);
            fail("Expected oversized payload rejection");
        } catch (IllegalArgumentException expected) {
            // Expected.
        }
    }

}
