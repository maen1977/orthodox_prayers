package com.orthodoxprayers.privateapp.data;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** Atomic local snapshot for the reviewed church directory. */
public final class ChurchDirectoryStore {
    private static final String FILE_NAME = "church_directory_cache.json";
    private static final String TEMP_FILE_NAME = FILE_NAME + ".tmp";
    private static final int MAX_BYTES = 2_000_000;

    private final File target;
    private final File temporary;

    public ChurchDirectoryStore(Context context) {
        File directory = context.getApplicationContext().getFilesDir();
        target = new File(directory, FILE_NAME);
        temporary = new File(directory, TEMP_FILE_NAME);
    }

    public synchronized JSONObject read() {
        if (!target.isFile() || target.length() <= 0 || target.length() > MAX_BYTES) return null;
        try (FileInputStream input = new FileInputStream(target)) {
            byte[] bytes = new byte[(int) target.length()];
            int offset = 0;
            while (offset < bytes.length) {
                int read = input.read(bytes, offset, bytes.length - offset);
                if (read < 0) return null;
                offset += read;
            }
            JSONObject payload = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
            return isSafeSnapshot(payload) ? payload : null;
        } catch (Exception ignored) {
            return null;
        }
    }

    public synchronized boolean write(JSONObject payload) {
        if (!isSafeSnapshot(payload)) return false;
        byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= 0 || bytes.length > MAX_BYTES) return false;
        try {
            File parent = target.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) return false;
            try (FileOutputStream output = new FileOutputStream(temporary, false)) {
                output.write(bytes);
                output.flush();
                output.getFD().sync();
            }
            if (target.exists() && !target.delete()) return false;
            if (!temporary.renameTo(target)) {
                temporary.delete();
                return false;
            }
            return true;
        } catch (Exception error) {
            temporary.delete();
            return false;
        }
    }

    private static boolean isSafeSnapshot(JSONObject payload) {
        if (payload == null || payload.optInt("schema_version", 0) < 2) return false;
        JSONArray churches = payload.optJSONArray("churches");
        if (churches == null || churches.length() == 0 || churches.length() > 2000) return false;
        if (payload.optInt("count", -1) != churches.length()) return false;
        if (payload.optJSONObject("directory_grouping") == null) return false;
        for (int i = 0; i < churches.length(); i++) {
            JSONObject church = churches.optJSONObject(i);
            if (church == null) return false;
            if (church.optString("id", "").trim().isEmpty()) return false;
            if (church.optString("source_id", "").trim().isEmpty()) return false;
            if (!church.optString("url", "").startsWith("https://")) return false;
            if (church.optString("region_id", "").trim().isEmpty()) return false;
        }
        return true;
    }
}
