# Daily-data signing public key

- Algorithm: RSA 3072-bit
- Payload signature: SHA-256 with RSA (PKCS#1 v1.5)
- DER public-key SHA-256: `cff1882f2ba6d6ee2b5b4621cd88a29242a988b845c9fa288f095f72cfe8e113`
- PEM public key: `data_signing_public_key.pub`
- Android DER resource: `app/src/main/res/raw/data_signing_public_key.der`

The matching private key is deliberately outside the project archive. Store it in GitHub Actions as `DATA_SIGNING_PRIVATE_KEY_B64`; never commit it.
