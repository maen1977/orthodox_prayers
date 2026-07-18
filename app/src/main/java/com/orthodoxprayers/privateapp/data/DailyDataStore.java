package com.orthodoxprayers.privateapp.data;

import android.content.Context;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Atomic, language-scoped storage for exact signed daily payload bytes.
 *
 * The JSON and detached signature are never rewritten after verification. Each
 * language gets an independent current/backup pair and up to 30 dated snapshots,
 * so switching languages cannot delete another language's trusted cache.
 */
public final class DailyDataStore {
    private static final String DIRECTORY = "trusted_daily_data";
    private static final String CURRENT_REFERENCE = "current.ref";
    private static final String BACKUP_REFERENCE = "backup.ref";
    private static final String ARCHIVE_DIRECTORY = "archive";
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
    private final File archiveDirectory;
    private final File currentReference;
    private final File backupReference;
    private final FaultInjector faultInjector;

    public DailyDataStore(Context context) {
        this(context, "ar");
    }

    public DailyDataStore(Context context, String language) {
        File files = context.getApplicationContext().getFilesDir();
        String lane = DataContract.normalizeLanguage(language);
        File scoped = new File(new File(files, DIRECTORY), lane);
        migrateLegacyStoreIfNeeded(new File(files, DIRECTORY), scoped);
        directory = scoped;
        archiveDirectory = new File(directory, ARCHIVE_DIRECTORY);
        currentReference = new File(directory, CURRENT_REFERENCE);
        backupReference = new File(directory, BACKUP_REFERENCE);
        faultInjector = NO_FAULTS;
    }

    /** Test constructor retaining the historical single-directory layout. */
    DailyDataStore(File filesDirectory) {
        this(filesDirectory, NO_FAULTS);
    }

    /** Test constructor retaining the historical single-directory layout. */
    DailyDataStore(File filesDirectory, FaultInjector faultInjector) {
        directory = new File(filesDirectory, DIRECTORY);
        archiveDirectory = new File(directory, ARCHIVE_DIRECTORY);
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

    public synchronized StoredPayload readDate(String dateIso) throws Exception {
        if (!isSafeDate(dateIso)) return null;
        return readReferenced(new File(archiveDirectory, dateIso + ".ref"));
    }

    public synchronized List<String> availableDates() {
        if (!archiveDirectory.isDirectory()) return Collections.emptyList();
        File[] refs = archiveDirectory.listFiles((dir, name) -> name.matches("\\d{4}-\\d{2}-\\d{2}\\.ref"));
        if (refs == null || refs.length == 0) return Collections.emptyList();
        ArrayList<String> dates = new ArrayList<>();
        for (File ref : refs) dates.add(ref.getName().substring(0, 10));
        dates.sort(Collections.reverseOrder());
        return dates;
    }

    /**
     * Commit order is deliberate:
     * 1. fully sync the immutable generation;
     * 2. point backup.ref to the last known-good current generation;
     * 3. atomically switch current.ref as the final throwing operation;
     * 4. best-effort index the generation by date and prune old snapshots.
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

            writeReferenceAtomically(currentReference, newGeneration);
            currentCommitted = true;
            indexDatedSnapshot(json, newGeneration);
            pruneArchiveReferences();
            cleanupUnreferencedGenerations();
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
        if (generation != null && !allReferencedGenerations().contains(generation)) {
            deleteRecursively(new File(directory, generation));
        }
    }

    private void indexDatedSnapshot(byte[] json, String generation) {
        try {
            JSONObject payload = new JSONObject(new String(json, StandardCharsets.UTF_8));
            String date = payload.optString("date_iso", payload.optString("date", "")).trim();
            if (!isSafeDate(date)) return;
            if (!archiveDirectory.isDirectory() && !archiveDirectory.mkdirs() && !archiveDirectory.isDirectory()) return;
            writeReferenceAtomically(new File(archiveDirectory, date + ".ref"), generation);
        } catch (Exception ignored) {
            // Test payloads and legacy imports may not be JSON. Current/backup remain valid.
        }
    }

    private void pruneArchiveReferences() {
        File[] refs = archiveDirectory.listFiles((dir, name) -> name.matches("\\d{4}-\\d{2}-\\d{2}\\.ref"));
        if (refs == null || refs.length <= DataContract.MAX_RETAINED_DAYS_PER_LANGUAGE) return;
        Arrays.sort(refs, (a, b) -> b.getName().compareTo(a.getName()));
        for (int i = DataContract.MAX_RETAINED_DAYS_PER_LANGUAGE; i < refs.length; i++) {
            deleteQuietly(refs[i]);
            deleteQuietly(new File(archiveDirectory, refs[i].getName() + ".tmp"));
        }
        syncDirectory(archiveDirectory);
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
                deleteQuietly(new File(target.getParentFile(), target.getName() + ".tmp"));
                syncDirectory(target.getParentFile());
            } else {
                writeReferenceAtomically(target, previousGeneration);
            }
            return null;
        } catch (Exception rollbackError) {
            return rollbackError;
        }
    }

    private void writeReferenceAtomically(File target, String generation) throws Exception {
        File parent = target.getParentFile();
        if (!parent.isDirectory() && !parent.mkdirs() && !parent.isDirectory()) {
            throw new IllegalStateException("reference_directory_unavailable");
        }
        File temporary = new File(parent, target.getName() + ".tmp");
        writeSynced(temporary, (generation + "\n").getBytes(StandardCharsets.UTF_8));
        moveReplacing(temporary, target);
        syncDirectory(parent);
    }

    private Set<String> allReferencedGenerations() {
        HashSet<String> result = new HashSet<>();
        addReference(result, currentReference);
        addReference(result, backupReference);
        File[] refs = archiveDirectory.listFiles((dir, name) -> name.endsWith(".ref"));
        if (refs != null) for (File ref : refs) addReference(result, ref);
        return result;
    }

    private void addReference(Set<String> output, File ref) {
        String value = readReferenceQuietly(ref);
        if (value != null) output.add(value);
    }

    private void cleanupUnreferencedGenerations() {
        Set<String> referenced = allReferencedGenerations();
        File[] files = directory.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (!file.isDirectory() || !file.getName().startsWith("generation-")) continue;
            if (!referenced.contains(file.getName())) deleteRecursively(file);
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
        if (target == null) return;
        try (FileInputStream ignored = new FileInputStream(target)) {
            ignored.getFD().sync();
        } catch (Exception ignored) {
            // Directory fsync is not supported by every Android filesystem.
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

    private static boolean isSafeDate(String value) {
        return value != null && value.matches("\\d{4}-\\d{2}-\\d{2}");
    }

    private static void migrateLegacyStoreIfNeeded(File legacyRoot, File scoped) {
        if (scoped.exists() || !new File(legacyRoot, CURRENT_REFERENCE).isFile()) return;
        try {
            copyRecursively(legacyRoot, scoped, true);
        } catch (Exception ignored) {
            // Legacy data is only a convenience; embedded signed data remains available.
        }
    }

    private static void copyRecursively(File source, File target, boolean skipLanguageDirectories) throws Exception {
        if (source.isDirectory()) {
            if (!target.isDirectory() && !target.mkdirs() && !target.isDirectory()) return;
            File[] children = source.listFiles();
            if (children == null) return;
            for (File child : children) {
                if (skipLanguageDirectories && child.isDirectory()
                        && ("ar".equals(child.getName()) || "en".equals(child.getName()) || "el".equals(child.getName()))) continue;
                copyRecursively(child, new File(target, child.getName()), false);
            }
        } else if (source.isFile()) {
            Files.copy(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
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
