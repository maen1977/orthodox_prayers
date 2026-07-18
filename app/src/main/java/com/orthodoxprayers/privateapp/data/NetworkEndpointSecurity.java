package com.orthodoxprayers.privateapp.data;

import java.net.URL;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/** Fail-closed endpoint policy for signed content downloads. */
public final class NetworkEndpointSecurity {
    private static final Set<String> ALLOWED_HOSTS;

    static {
        LinkedHashSet<String> hosts = new LinkedHashSet<>();
        hosts.add("raw.githubusercontent.com");
        ALLOWED_HOSTS = Collections.unmodifiableSet(hosts);
    }

    private NetworkEndpointSecurity() {}

    public static URL requireAllowedHttps(String value) throws Exception {
        URL url = new URL(value);
        if (!"https".equalsIgnoreCase(url.getProtocol())) {
            throw new IllegalStateException("https_required");
        }
        String host = url.getHost() == null ? "" : url.getHost().toLowerCase();
        if (!ALLOWED_HOSTS.contains(host)) {
            throw new IllegalStateException("endpoint_host_not_allowed:" + host);
        }
        if (url.getUserInfo() != null || url.getPort() != -1) {
            throw new IllegalStateException("endpoint_authority_invalid");
        }
        return url;
    }

    public static boolean isAllowedRedirect(URL original, URL redirected) {
        if (original == null || redirected == null) return false;
        return "https".equalsIgnoreCase(redirected.getProtocol())
                && original.getHost().equalsIgnoreCase(redirected.getHost())
                && redirected.getPort() == -1
                && redirected.getUserInfo() == null;
    }
}
