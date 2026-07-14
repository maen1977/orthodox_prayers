package com.orthodoxprayers.privateapp.data;

import java.security.PublicKey;
import java.security.Signature;
import java.util.Base64;

/** Pure-Java signature primitive kept separate so it can be unit-tested without Android. */
public final class CryptoVerifier {
    private CryptoVerifier() {}

    public static void verifySha256Rsa(PublicKey publicKey, byte[] payload, byte[] encodedSignature) throws Exception {
        if (publicKey == null) throw new IllegalStateException("public_key_missing");
        if (payload == null || payload.length == 0) throw new IllegalStateException("signed_payload_empty");
        if (encodedSignature == null || encodedSignature.length == 0) throw new IllegalStateException("signature_missing");

        byte[] signatureBytes;
        try {
            String encoded = new String(encodedSignature, java.nio.charset.StandardCharsets.US_ASCII).trim();
            signatureBytes = Base64.getDecoder().decode(encoded);
        } catch (IllegalArgumentException error) {
            throw new IllegalStateException("signature_encoding_invalid", error);
        }

        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(publicKey);
        verifier.update(payload);
        if (!verifier.verify(signatureBytes)) throw new IllegalStateException("signature_invalid");
    }
}
