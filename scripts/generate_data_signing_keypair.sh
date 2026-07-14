#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-$PWD/data-signing-keypair}"
mkdir -p "$output_dir"
private_key="$output_dir/orthodox_prayers_DATA_SIGNING_PRIVATE_KEY.pem"
public_key="$output_dir/data_signing_public_key.pub"
public_der="$output_dir/data_signing_public_key.der"

if [[ -e "$private_key" || -e "$public_key" || -e "$public_der" ]]; then
  echo "Refusing to overwrite an existing keypair in $output_dir" >&2
  exit 1
fi

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$private_key"
chmod 600 "$private_key"
openssl pkey -in "$private_key" -pubout -out "$public_key"
openssl pkey -in "$private_key" -pubout -outform DER -out "$public_der"
echo "Keypair generated. Keep $private_key offline and never commit it."
