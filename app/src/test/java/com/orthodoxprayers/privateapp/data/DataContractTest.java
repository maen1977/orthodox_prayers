package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class DataContractTest {
    @Test public void schemaRangeIsExplicitAndFailClosed() {
        assertFalse(DataContract.supportsSchema(8));
        assertTrue(DataContract.supportsSchema(9));
        assertFalse(DataContract.supportsSchema(10));
    }

    @Test public void onlySupportedLanguageLanesAreAccepted() {
        assertEquals("ar", DataContract.normalizeLanguage(null));
        assertEquals("ar", DataContract.normalizeLanguage("fr"));
        assertEquals("en", DataContract.normalizeLanguage("en"));
        assertEquals("el", DataContract.normalizeLanguage("el"));
    }
}
