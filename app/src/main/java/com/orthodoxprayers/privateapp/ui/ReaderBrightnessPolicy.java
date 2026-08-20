package com.orthodoxprayers.privateapp.ui;

/**
 * Keeps reader brightness separate from the device's current brightness.
 * A value of {@link #USE_SYSTEM} means that the reader must not override
 * the activity window brightness.
 */
public final class ReaderBrightnessPolicy {
    public static final int USE_SYSTEM = 0;

    private ReaderBrightnessPolicy() {}

    public static int normalize(int value) {
        if (value <= USE_SYSTEM) return USE_SYSTEM;
        return Math.max(20, Math.min(100, value));
    }

    public static boolean usesSystemBrightness(int value) {
        return normalize(value) == USE_SYSTEM;
    }

    /**
     * Cycles through the reader choices without changing the system setting
     * until the user explicitly selects a custom value.
     */
    public static int next(int value) {
        int current = normalize(value);
        if (current == USE_SYSTEM) return 80;
        if (current >= 100) return USE_SYSTEM;
        if (current >= 80) return 60;
        if (current >= 60) return 40;
        if (current >= 40) return 20;
        return 100;
    }
}
