package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.net.URL;
import org.junit.Test;

public final class NetworkEndpointSecurityTest {
    @Test public void acceptsOnlyPinnedHttpsHost() throws Exception {
        NetworkEndpointSecurity.requireAllowedHttps("https://raw.githubusercontent.com/maen1977/orthodox_prayers/verified-data/data/calendar/today.json");
        for (String unsafe : new String[]{
                "http://raw.githubusercontent.com/a/b",
                "https://example.com/a",
                "https://user@raw.githubusercontent.com/a/b",
                "https://raw.githubusercontent.com:443/a/b"
        }) {
            try {
                NetworkEndpointSecurity.requireAllowedHttps(unsafe);
                fail("Expected rejection: " + unsafe);
            } catch (IllegalStateException expected) {
                // Fail closed.
            }
        }
    }

    @Test public void redirectsMustStayOnTheSameHttpsHost() throws Exception {
        URL original = new URL("https://raw.githubusercontent.com/a/b");
        assertTrue(NetworkEndpointSecurity.isAllowedRedirect(original, new URL("https://raw.githubusercontent.com/a/c")));
        assertFalse(NetworkEndpointSecurity.isAllowedRedirect(original, new URL("https://github.com/a/c")));
        assertFalse(NetworkEndpointSecurity.isAllowedRedirect(original, new URL("http://raw.githubusercontent.com/a/c")));
    }
}
