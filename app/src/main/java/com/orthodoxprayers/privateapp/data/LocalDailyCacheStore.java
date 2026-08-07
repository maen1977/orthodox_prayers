package com.orthodoxprayers.privateapp.data;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;

/**
 * Private atomic cache for the locally generated nine-day package.
 *
 * This cache is not a trust boundary: its contents are deterministically rebuilt
 * from APK assets. A SHA-256 sidecar only detects torn/corrupt writes so startup
 * can discard them instead of blocking while trying to repair data on the UI
 * thread.
 */
public final class LocalDailyCacheStore {
    private static final String DIRECTORY = "local_daily_cache";
    private static final String PAYLOAD = "current.json";
    private static final String HASH = "current.sha256";
    private static final int MAX_BYTES = DataContract.MAX_SIGNED_PAYLOAD_BYTES;

    private final File directory;
    private final File payloadFile;
    private final File hashFile;

    public LocalDailyCacheStore(Context context) {
        directory = new File(context.getApplicationContext().getFilesDir(), DIRECTORY);
        payloadFile = new File(directory, PAYLOAD);
        hashFile = new File(directory, HASH);
    }

    public synchronized byte[] read() {
        try {
            if (!payloadFile.isFile() || !hashFile.isFile()) return null;
            byte[] payload = readLimited(payloadFile, MAX_BYTES);
            String expected = new String(readLimited(hashFile, 256), StandardCharsets.US_ASCII).trim();
            if (!expected.matches("[0-9a-fA-F]{64}")) return null;
            if (!expected.equalsIgnoreCase(sha256(payload))) return null;
            return payload;
        } catch (Exception ignored) {
            return null;
        }
    }

    public synchronized void save(byte[] payload) throws Exception {
        if (payload == null || payload.length == 0 || payload.length > MAX_BYTES) {
            throw new IllegalArgumentException("local_daily_cache_size_invalid");
        }
        if (!directory.isDirectory() && !directory.mkdirs() && !directory.isDirectory()) {
            throw new IllegalStateException("local_daily_cache_directory_unavailable");
        }
        File payloadTemp = new File(directory, PAYLOAD + ".tmp");
        File hashTemp = new File(directory, HASH + ".tmp");
        writeSynced(payloadTemp, payload);
        writeSynced(hashTemp, (sha256(payload) + "\n").getBytes(StandardCharsets.US_ASCII));
        moveReplacing(payloadTemp, payloadFile);
        moveReplacing(hashTemp, hashFile);
    }

    public synchronized void clear() {
        payloadFile.delete();
        hashFile.delete();
        new File(directory, PAYLOAD + ".tmp").delete();
        new File(directory, HASH + ".tmp").delete();
    }

    private static byte[] readLimited(File file, int maxBytes) throws Exception {
        long length = file.length();
        if (length <= 0 || length > maxBytes) throw new IllegalStateException("local_daily_cache_file_size_invalid");
        byte[] output = new byte[(int) length];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < output.length) {
                int read = input.read(output, offset, output.length - offset);
                if (read < 0) break;
                offset += read;
            }
            if (offset != output.length) throw new IllegalStateException("local_daily_cache_truncated");
        }
        return output;
    }

    private static void writeSynced(File file, byte[] bytes) throws Exception {
        try (FileOutputStream output = new FileOutputStream(file, false)) {
            output.write(bytes);
            output.flush();
            output.getFD().sync();
        }
    }

    private static void moveReplacing(File source, File target) throws Exception {
        try {
            Files.move(source.toPath(), target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (java.nio.file.AtomicMoveNotSupportedException unsupported) {
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static String sha256(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte value : digest) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 0xff));
        return result.toString();
    }
}
