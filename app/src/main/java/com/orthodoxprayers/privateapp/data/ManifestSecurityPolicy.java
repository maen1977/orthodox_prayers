package com.orthodoxprayers.privateapp.data;

import java.time.Duration;
import java.time.Instant;

/** Central fail-closed and replay-window rules for signed update manifests. */
public final class ManifestSecurityPolicy {
    private static final Duration MAX_FUTURE_PUBLICATION_SKEW = Duration.ofMinutes(30);
    private static final Duration MAX_VALIDITY_WINDOW = Duration.ofHours(72);
    private static final Duration MAX_DEVICE_CLOCK_SKEW = Duration.ofHours(6);

    private ManifestSecurityPolicy() {}

    public static void validatePublicationWindow(String publishedValue, String validUntilValue) {
        String publishedText = safe(publishedValue);
        String validUntilText = safe(validUntilValue);
        if (publishedText.isEmpty() && validUntilText.isEmpty()) return; // Legacy signed manifest.
        if (publishedText.isEmpty()) {
            throw new IllegalStateException("manifest_publication_time_missing");
        }
        try {
            Instant published = Instant.parse(publishedText);
            Instant now = Instant.now();
            if (published.isAfter(now.plus(MAX_FUTURE_PUBLICATION_SKEW))) {
                throw new IllegalStateException("manifest_publication_time_future");
            }
            if (validUntilText.isEmpty()) return; // Compatible publication-time-only manifest.

            Instant validUntil = Instant.parse(validUntilText);
            Duration window = Duration.between(published, validUntil);
            if (window.isNegative() || window.isZero()
                    || window.compareTo(MAX_VALIDITY_WINDOW) > 0) {
                throw new IllegalStateException("manifest_validity_window_invalid");
            }
            if (now.isAfter(validUntil.plus(MAX_DEVICE_CLOCK_SKEW))) {
                throw new IllegalStateException("manifest_expired");
            }
        } catch (IllegalStateException error) {
            throw error;
        } catch (Exception error) {
            throw new IllegalStateException("manifest_publication_time_invalid");
        }
    }

    public static boolean mustFailClosed(Throwable error) {
        if (error == null) return false;
        String message = safe(error.getMessage());
        if (message.startsWith("manifest_http_")
                || message.startsWith("manifest_date_mismatch")) {
            return false;
        }
        return message.startsWith("manifest_")
                || message.startsWith("signature_")
                || message.startsWith("signed_")
                || message.startsWith("public_key_")
                || message.startsWith("unexpected_content_type");
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }
}
