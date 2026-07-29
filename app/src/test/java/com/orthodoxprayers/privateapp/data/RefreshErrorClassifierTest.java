package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import java.net.SocketTimeoutException;
import java.net.UnknownHostException;

import javax.net.ssl.SSLHandshakeException;

import org.junit.Test;

public final class RefreshErrorClassifierTest {
    @Test public void distinguishesDnsFromActualOfflineState() {
        assertEquals(
                "network_dns_unavailable",
                RefreshErrorClassifier.classify(new UnknownHostException("raw.githubusercontent.com"))
        );
    }

    @Test public void classifiesServerAndTlsFailuresTruthfully() {
        assertEquals(
                "server_timeout",
                RefreshErrorClassifier.classify(new SocketTimeoutException("timed out"))
        );
        assertEquals(
                "secure_connection_failed",
                RefreshErrorClassifier.classify(new SSLHandshakeException("handshake failed"))
        );
        assertEquals(
                "server_manifest_not_ready",
                RefreshErrorClassifier.classify(new IllegalStateException("manifest_http_404"))
        );
    }

    @Test public void neverMislabelsSignedDataRejectionAsInternetFailure() {
        assertEquals(
                "invalid_signature_invalid",
                RefreshErrorClassifier.classify(new IllegalStateException("signature_invalid"))
        );
        assertEquals(
                "invalid_same_day_content_regression:gospel:body",
                RefreshErrorClassifier.classify(
                        new IllegalStateException("same_day_content_regression:gospel:body")
                )
        );
    }
}
