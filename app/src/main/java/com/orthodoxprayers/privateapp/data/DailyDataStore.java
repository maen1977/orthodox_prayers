package com.orthodoxprayers.privateapp.data;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

/** Stores signed daily data in immutable generations selected by atomic reference files. */
public final class DailyDataStore {
    private static final String DIRECTORY = "trusted_daily_data";
    private static final String CURRENT_REFERENCE = "current.ref";
    private static final String BACKUP_REFERENCE = "backup.ref";
    private static final int MAX_JSON_BYTES = 2_000_000;
    private static final int MAX_SIGNATURE_BYTES = 16_384;
    private static final int MAX_REFERENCE_BYTES = 128;

    interface FaultInjector {
        void afterGenerationSynced() throws Exception;
        void afterBackupCommitted() throws Exception;
    }

    private static final FaultInjector NO_FAULTS = new FaultInjector() {
        @Override public void afterGenerationSynced() {}
        @Override public void afterBackupCommitted() {}
    };

    private final File directory;
    private final File currentReference;
    private final File backupReference;
    private final FaultInjector faultInjector;

    public DailyDataStore(Context context) {
        this(context.getFilesDir(), NO_FAULTS);
    }

    DailyDataStore(File filesDirectory) {
        this(filesDirectory, NO_FAULTS);
    }

    DailyDataStore(File filesDirectory, FaultInjector faultInjector) {
        directory = new File(filesDirectory, DIRECTORY);
        currentReference = new File(directory, CURRENT_REFERENCE);
        backupReference = new File(directory, BACKUP_REFERENCE);
        this.faultInjector = faultInjector == null ? NO_FAULTS : faultInjector;
    }

    public synchronized StoredPayload readCurrent() throws Exception {
        return readReferenced(currentReference);
    }

    public synchronized StoredPayload readBackup() throws Exception {
        return readReferenced(backupReference);
    }

    /**
     * Commit order is deliberate:
     * 1. fully sync the immutable generation;
     * 2. point backup.ref to the last known-good current generation;
     * 3. atomically switch current.ref as the final throwing operation.
     *
     * If anything fails before step 3, the old current reference remains valid and the
     * previous backup reference is restored. No reference is ever left pointing at a
     * generation that this method deletes.
     */
    public synchronized void saveVerified(byte[] json, byte[] signature) throws Exception {
        validatePayload(json, signature);
        ensureDirectory();

        String previousCurrent = readReference(currentReference);
        String previousBackup = readReference(backupReference);
        String newGeneration = "generation-" + System.currentTimeMillis() + "-" + UUID.randomUUID();
        File generationDirectory = new File(directory, newGeneration);
        if (!generationDirectory.mkdir()) throw new IllegalStateException("generation_directory_unavailable");

        boolean currentCommitted = false;
        try {
            writeSynced(new File(generationDirectory, "today.json"), json);
            writeSynced(new File(generationDirectory, "today.json.sig"), signature);
            syncDirectory(generationDirectory);
            faultInjector.afterGenerationSynced();

            if (previousCurrent != null) {
                writeReferenceAtomically(backupReference, previousCurrent);
                faultInjector.afterBackupCommitted();
            }

            // Final throwing commit step. Everything after this is best-effort cleanup only.
            writeReferenceAtomically(currentReference, newGeneration);
            currentCommitted = true;
            cleanupGenerations(newGeneration, previousCurrent != null ? previousCurrent : previousBackup);
        } catch (Exception error) {
            if (!currentCommitted) {
                Exception rollbackError = restoreReference(backupReference, previousBackup);
                deleteRecursively(generationDirectory);
                if (rollbackError != null) error.addSuppressed(rollbackError);
            }
            throw error;
        }
    }

    public synchronized void deleteCurrent() {
        String generation = readReferenceQuietly(currentReference);
        currentReference.delete();
        deleteQuietly(new File(directory, CURRENT_REFERENCE + ".tmp"));
        if (generation != null && !generation.equals(readReferenceQuietly(backupReference))) {
            deleteRecursively(new File(directory, generation));
        }
    }

    private StoredPayload readReferenced(File reference) throws Exception {
        String generation = readReference(reference);
        if (generation == null) return null;
        File generationDirectory = safeGenerationDirectory(generation);
        File json = new File(generationDirectory, "today.json");
        File signature = new File(generationDirectory, "today.json.sig");
        if (!json.isFile() || !signature.isFile()) throw new IllegalStateException("stored_pair_incomplete");
        return new StoredPayload(readLimited(json, MAX_JSON_BYTES), readLimited(signature, MAX_SIGNATURE_BYTES));
    }

    private File safeGenerationDirectory(String generation) throws Exception {
        if (!generation.matches("generation-[A-Za-z0-9._-]+")) throw new IllegalStateException("stored_reference_invalid");
        File candidate = new File(directory, generation);
        String root = directory.getCanonicalPath() + File.separator;
        String resolved = candidate.getCanonicalPath() + File.separator;
        if (!resolved.startsWith(root)) throw new IllegalStateException("stored_reference_escape");
        return candidate;
    }

    private String readReference(File reference) throws Exception {
        if (!reference.isFile()) return null;
        String value = new String(readLimited(reference, MAX_REFERENCE_BYTES), StandardCharsets.UTF_8).trim();
        return value.isEmpty() ? null : value;
    }

    private String readReferenceQuietly(File reference) {
        try { return readReference(reference); }
        catch (Exception ignored) { return null; }
    }

    private Exception restoreReference(File target, String previousGeneration) {
        try {
            if (previousGeneration == null) {
                deleteQuietly(target);
                deleteQuietly(new File(directory, target.getName() + ".tmp"));
                syncDirectory(directory);
            } else {
                writeReferenceAtomically(target, previousGeneration);
            }
            return null;
        } catch (Exception rollbackError) {
            return rollbackError;
        }
    }

    private void writeReferenceAtomically(File target, String generation) throws Exception {
        File temporary = new File(directory, target.getName() + ".tmp");
        writeSynced(temporary, (generation + "\n").getBytes(StandardCharsets.UTF_8));
        moveReplacing(temporary, target);
        syncDirectory(directory);
    }

    private void cleanupGenerations(String current, String backup) {
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (!file.isDirectory() || !file.getName().startsWith("generation-")) continue;
            if (file.getName().equals(current) || file.getName().equals(backup)) continue;
            deleteRecursively(file);
        }
    }

    private static void validatePayload(byte[] json, byte[] signature) {
        if (json == null || json.length == 0 || json.length > MAX_JSON_BYTES) throw new IllegalArgumentException("invalid_json_size");
        if (signature == null || signature.length == 0 || signature.length > MAX_SIGNATURE_BYTES) throw new IllegalArgumentException("invalid_signature_size");
    }

    private void ensureDirectory() throws Exception {
        if (!directory.isDirectory() && !directory.mkdirs() && !directory.isDirectory()) {
            throw new IllegalStateException("cache_directory_unavailable");
        }
    }

    private static void writeSynced(File target, byte[] bytes) throws Exception {
        try (FileOutputStream output = new FileOutputStream(target, false)) {
            output.write(bytes);
            output.flush();
            output.getFD().sync();
        }
    }

    private static void syncDirectory(File target) {
        try (FileInputStream ignored = new FileInputStream(target)) {
            ignored.getFD().sync();
        } catch (Exception ignored) {
            // Directory fsync is not supported by every Android filesystem; file fsync still applies.
        }
    }

    private static void moveReplacing(File source, File target) throws Exception {
        try {
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (AtomicMoveNotSupportedException error) {
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static byte[] readLimited(File file, int maxBytes) throws Exception {
        long length = file.length();
        if (length <= 0 || length > maxBytes) throw new IllegalStateException("stored_file_size_invalid");
        byte[] data = new byte[(int) length];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < data.length) {
                int read = input.read(data, offset, data.length - offset);
                if (read < 0) break;
                offset += read;
            }
            if (offset != data.length) throw new IllegalStateException("stored_file_truncated");
        }
        return data;
    }

    private static void deleteQuietly(File file) {
        try { if (file != null) file.delete(); }
        catch (Exception ignored) {}
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        File[] children = file.listFiles();
        if (children != null) for (File child : children) deleteRecursively(child);
        deleteQuietly(file);
    }

    public static final class StoredPayload {
        public final byte[] json;
        public final byte[] signature;

        StoredPayload(byte[] json, byte[] signature) {
            this.json = json;
            this.signature = signature;
        }
    }
}
