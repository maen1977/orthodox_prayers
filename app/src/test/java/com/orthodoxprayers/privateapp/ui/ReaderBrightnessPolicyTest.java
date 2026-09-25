package com.orthodoxprayers.privateapp.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class ReaderBrightnessPolicyTest {
    @Test
    public void systemBrightnessIsTheDefaultAndDoesNotOverrideTheWindow() {
        assertEquals(ReaderBrightnessPolicy.USE_SYSTEM, ReaderBrightnessPolicy.normalize(0));
        assertTrue(ReaderBrightnessPolicy.usesSystemBrightness(ReaderBrightnessPolicy.USE_SYSTEM));
        assertFalse(ReaderBrightnessPolicy.usesSystemBrightness(80));
    }

    @Test
    public void invalidValuesAreNormalizedSafely() {
        assertEquals(ReaderBrightnessPolicy.USE_SYSTEM, ReaderBrightnessPolicy.normalize(-1));
        assertEquals(20, ReaderBrightnessPolicy.normalize(10));
        assertEquals(100, ReaderBrightnessPolicy.normalize(140));
    }

    @Test
    public void cycleStartsWithAnExplicitReaderChoice() {
        assertEquals(80, ReaderBrightnessPolicy.next(ReaderBrightnessPolicy.USE_SYSTEM));
        assertEquals(60, ReaderBrightnessPolicy.next(80));
        assertEquals(40, ReaderBrightnessPolicy.next(60));
        assertEquals(20, ReaderBrightnessPolicy.next(40));
        assertEquals(100, ReaderBrightnessPolicy.next(20));
        assertEquals(ReaderBrightnessPolicy.USE_SYSTEM, ReaderBrightnessPolicy.next(100));
    }
}
