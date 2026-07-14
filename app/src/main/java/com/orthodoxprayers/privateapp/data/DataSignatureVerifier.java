package com.orthodoxprayers.privateapp.data;

import android.content.Context;
import com.orthodoxprayers.privateapp.R;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;

/** Verifies detached SHA-256/RSA signatures for daily data before parsing it. */
public final class DataSignatureVerifier {
    private static final int MAX_PUBLIC_KEY_BYTES = 8_192;
    private final PublicKey publicKey;

    public DataSignatureVerifier(Context context) {
        try (InputStream input = context.getResources().openRawResource(R.raw.data_signing_public_key)) {
            byte[] keyBytes = readLimited(input, MAX_PUBLIC_KEY_BYTES);
            publicKey = KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(keyBytes));
        } catch (Exception error) {
            throw new IllegalStateException("data_public_key_invalid", error);
        }
    }

    public void verify(byte[] payload, byte[] encodedSignature) throws Exception {
        CryptoVerifier.verifySha256Rsa(publicKey, payload, encodedSignature);
    }

    private static byte[] readLimited(InputStream input, int maxBytes) throws Exception {
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[2048];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) throw new IllegalStateException("public_key_too_large");
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }
}
