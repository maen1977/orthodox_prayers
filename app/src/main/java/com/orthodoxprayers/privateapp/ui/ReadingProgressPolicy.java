package com.orthodoxprayers.privateapp.ui;

/** Pure reader-progress rules shared by the reader and home screen. */
public final class ReadingProgressPolicy {
    private ReadingProgressPolicy() {}

    public static int percentFromLastVisible(int lastVisiblePosition, int itemCount) {
        if (itemCount <= 0 || lastVisiblePosition < 0) return 0;
        int boundedLast = Math.min(lastVisiblePosition, itemCount - 1);
        return Math.max(0, Math.min(100, Math.round(((boundedLast + 1) * 100f) / itemCount)));
    }

    public static boolean isResumable(int percent) {
        return percent > 0 && percent < 100;
    }
}
