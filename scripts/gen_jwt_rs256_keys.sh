#!/usr/bin/env bash
# Generate RSA key pair for QuantumFintek RS256 JWT signing.
# Usage:
#   ./scripts/gen_jwt_rs256_keys.sh [kid]
# Example:
#   ./scripts/gen_jwt_rs256_keys.sh qf-key-2

set -euo pipefail

KID="${1:-qf-key-1}"
OUT_DIR="${JWT_KEY_OUT_DIR:-./secrets/jwt}"
mkdir -p "$OUT_DIR"

PRIV="$OUT_DIR/${KID}.private.pem"
PUB="$OUT_DIR/${KID}.public.pem"

if [[ -f "$PRIV" ]]; then
  echo "Refusing to overwrite existing $PRIV" >&2
  exit 1
fi

openssl genrsa -out "$PRIV" 2048
openssl rsa -in "$PRIV" -pubout -out "$PUB"
chmod 600 "$PRIV"
chmod 644 "$PUB"

echo "Generated:"
echo "  private: $PRIV"
echo "  public:  $PUB"
echo
echo "Set in environment / secret manager:"
echo "  JWT_ALGORITHM=RS256"
echo "  JWT_KEY_ID=$KID"
echo "  JWT_PRIVATE_KEY_PEM=<(contents of $PRIV)>"
echo "  JWT_PUBLIC_KEY_PEM=<(contents of $PUB)>"
echo
echo "Rotation:"
echo "  1. Generate new kid (e.g. qf-key-2) with this script"
echo "  2. Set JWT_PREVIOUS_PUBLIC_KEYS_JSON to include the OLD public PEM under the OLD kid"
echo "  3. Point JWT_KEY_ID + JWT_PRIVATE_KEY_PEM + JWT_PUBLIC_KEY_PEM at the NEW key"
echo "  4. After access_token_expire + refresh_token_expire, drop the previous public key"
echo "  5. Restart API (clear get_key_ring lru_cache via process restart)"
