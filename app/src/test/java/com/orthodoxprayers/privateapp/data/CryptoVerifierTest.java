package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertThrows;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.util.Base64;

import org.junit.Test;

public final class CryptoVerifierTest {
    @Test
    public void acceptsAuthenticPayloadAndRejectsTampering() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair pair = generator.generateKeyPair();
        byte[] payload = "trusted daily data".getBytes(StandardCharsets.UTF_8);

        Signature signer = Signature.getInstance("SHA256withRSA");
        signer.initSign(pair.getPrivate());
        signer.update(payload);
        byte[] encoded = Base64.getEncoder().encode(signer.sign());

        CryptoVerifier.verifySha256Rsa(pair.getPublic(), payload, encoded);
        assertThrows(IllegalStateException.class, () ->
                CryptoVerifier.verifySha256Rsa(
                        pair.getPublic(),
                        "tampered daily data".getBytes(StandardCharsets.UTF_8),
                        encoded
                )
        );
    }

    @Test
    public void rejectsMalformedBase64() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair pair = generator.generateKeyPair();
        assertThrows(IllegalStateException.class, () ->
                CryptoVerifier.verifySha256Rsa(pair.getPublic(), new byte[]{1}, "not-base64!".getBytes(StandardCharsets.US_ASCII))
        );
    }
}
