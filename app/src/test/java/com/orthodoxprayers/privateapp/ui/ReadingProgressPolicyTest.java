package com.orthodoxprayers.privateapp.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class ReadingProgressPolicyTest {
    @Test public void progressIsClampedAndUsesLastVisibleRow() {
        assertEquals(0, ReadingProgressPolicy.percentFromLastVisible(-1, 100));
        assertEquals(1, ReadingProgressPolicy.percentFromLastVisible(0, 100));
        assertEquals(50, ReadingProgressPolicy.percentFromLastVisible(49, 100));
        assertEquals(100, ReadingProgressPolicy.percentFromLastVisible(150, 100));
    }

    @Test public void onlyPartialProgressIsResumable() {
        assertFalse(ReadingProgressPolicy.isResumable(0));
        assertTrue(ReadingProgressPolicy.isResumable(1));
        assertTrue(ReadingProgressPolicy.isResumable(99));
        assertFalse(ReadingProgressPolicy.isResumable(100));
    }
}
