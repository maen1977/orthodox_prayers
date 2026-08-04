package com.orthodoxprayers.privateapp.data;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public final class ManifestSecurityPolicyTest {
    @Test
    public void securityAndIntegrityFailuresAreFailClosed() {
        assertTrue(ManifestSecurityPolicy.mustFailClosed(
                new IllegalStateException("manifest_expired")));
        assertTrue(ManifestSecurityPolicy.mustFailClosed(
                new IllegalStateException("signature_invalid")));
        assertTrue(ManifestSecurityPolicy.mustFailClosed(
                new IllegalStateException("unexpected_content_type:text/html")));
    }

    @Test
    public void AvailabilityFailuresMayUseTheSignedLegacyEndpoint() {
        assertFalse(ManifestSecurityPolicy.mustFailClosed(
                new IllegalStateException("manifest_http_404")));
        assertFalse(ManifestSecurityPolicy.mustFailClosed(
                new IllegalStateException("manifest_date_mismatch")));
        assertFalse(ManifestSecurityPolicy.mustFailClosed(null));
    }
}
