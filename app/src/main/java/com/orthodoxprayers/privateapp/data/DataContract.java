package com.orthodoxprayers.privateapp.data;

/** Central Android-side contract for signed daily content. */
public final class DataContract {
    public static final int MIN_SUPPORTED_SCHEMA_VERSION = 9;
    public static final int MAX_SUPPORTED_SCHEMA_VERSION = 10;
    public static final int MIN_LANGUAGE_LANE_SCHEMA_VERSION = 2;
    public static final int MAX_RETAINED_DAYS_PER_LANGUAGE = 30;
    /** Maximum exact signed language payload accepted from the public update manifest. */
    public static final int MAX_SIGNED_PAYLOAD_BYTES = 12_000_000;

    private DataContract() {}

    public static boolean supportsSchema(int version) {
        return version >= MIN_SUPPORTED_SCHEMA_VERSION && version <= MAX_SUPPORTED_SCHEMA_VERSION;
    }

    public static String normalizeLanguage(String language) {
        String value = language == null ? "" : language.trim();
        if ("en".equals(value) || "el".equals(value)) return value;
        return "ar";
    }
}
