package com.orthodoxprayers.privateapp.data;

import java.io.IOException;
import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;

import javax.net.ssl.SSLException;

/** Maps refresh failures to truthful diagnostics instead of calling every failure "offline". */
public final class RefreshErrorClassifier {
    private RefreshErrorClassifier() {}

    public static String classify(Throwable error) {
        if (error == null) return "unexpected_refresh_error";
        String message = safeMessage(error);

        if (message.startsWith("app_update_required")
                || message.startsWith("manifest_revision_rollback")
                || message.startsWith("manifest_unavailable_after_acceptance")
                || message.startsWith("date_not_ready")) {
            return message;
        }
        if (message.startsWith("manifest_http_404")) return "server_manifest_not_ready";
        if (message.startsWith("manifest_http_")) return "server_manifest_http:" + suffix(message);
        if (message.startsWith("signature_http_404") || message.startsWith("http_404")) {
            return "server_data_not_ready";
        }
        if (message.startsWith("signature_http_") || message.startsWith("http_")) {
            return "server_http:" + suffix(message);
        }
        if (message.startsWith("manifest_date_mismatch")) return "server_manifest_not_ready";

        if (isInvalidPayload(message)) return "invalid_" + message;

        for (Throwable current = error; current != null; current = current.getCause()) {
            if (current instanceof UnknownHostException) return "network_dns_unavailable";
            if (current instanceof NoRouteToHostException) return "network_unreachable";
            if (current instanceof SocketTimeoutException) return "server_timeout";
            if (current instanceof ConnectException) return "server_connection_failed";
            if (current instanceof SSLException) return "secure_connection_failed";
            if (current instanceof IOException) return "network_io_error";
        }
        return "unexpected_refresh_error:" + error.getClass().getSimpleName();
    }

    private static boolean isInvalidPayload(String message) {
        return message.contains("payload")
                || message.contains("schema")
                || message.contains("signature")
                || message.contains("signed_")
                || message.contains("missing")
                || message.contains("incomplete")
                || message.contains("integrity")
                || message.contains("content_type")
                || message.contains("too_large")
                || message.contains("translation")
                || message.contains("diacritization")
                || message.contains("text_unverified")
                || message.contains("hash_invalid")
                || message.contains("unverified_scripture")
                || message.contains("service_")
                || message.contains("language_lane")
                || message.contains("localized_script")
                || message.contains("date_in_future")
                || message.contains("date_invalid")
                || message.contains("same_day_content_regression")
                || message.contains("rolling_week");
    }

    private static String safeMessage(Throwable error) {
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) return error.getClass().getSimpleName();
        return message.trim();
    }

    private static String suffix(String message) {
        int marker = message.lastIndexOf('_');
        return marker >= 0 && marker + 1 < message.length()
                ? message.substring(marker + 1)
                : message;
    }
}
