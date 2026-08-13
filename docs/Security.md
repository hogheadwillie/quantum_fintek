# Security Architecture

## Authentication

- **Access tokens**: Short-lived JWT (default 30 min) signed with **RS256** (`kid` in header)
- **Refresh tokens**: JWT + Redis session record; rotated on every `/auth/refresh`
- **Revocation**: Access JTI denylist in Redis; refresh revoke / logout-all
- **ForwardAuth**: Traefik → `/auth/verify` (respects denylist)

## JWT algorithm & key rotation (RS256)

### Config

| Variable | Purpose |
|----------|---------|
| `JWT_ALGORITHM` | `RS256` (default). `HS256` only for local dev without PEMs |
| `JWT_KEY_ID` | Active signing key id (`kid` header) |
| `JWT_PRIVATE_KEY_PEM` | Active RSA private key (required in production) |
| `JWT_PUBLIC_KEY_PEM` | Active RSA public key |
| `JWT_PREVIOUS_PUBLIC_KEYS_JSON` | `{"old-kid":"-----BEGIN PUBLIC KEY-----..."}` still accepted for verify |
| `SECRET_KEY` | HS256 fallback / other secrets; must not be default in production |

Production **rejects** HS* and missing private PEM (`Settings` validator).

### Sign / verify

- New tokens are signed with the **active** private key and header `{"kid": "...", "alg": "RS256"}`.
- Verification reads `kid`, selects public material from the key ring, and **rejects** disallowed `alg` (no algorithm confusion).
- Unknown `kid` → invalid token.

### Rotation procedure

1. Generate a new key pair: `./scripts/gen_jwt_rs256_keys.sh qf-key-2`
2. Keep the **previous** public key available:

   ```bash
   JWT_PREVIOUS_PUBLIC_KEYS_JSON={"qf-key-1":"$(awk 'NF {sub(/\r/, ""); printf "%s\\n", $0;}' secrets/jwt/qf-key-1.public.pem)"}
   ```

3. Promote the new key:

   ```bash
   JWT_KEY_ID=qf-key-2
   JWT_PRIVATE_KEY_PEM=...  # qf-key-2 private
   JWT_PUBLIC_KEY_PEM=...   # qf-key-2 public
   ```

4. Rolling-restart API processes (key ring is process-cached).
5. After **max(access TTL, refresh TTL)** (and any offline token grace), remove the old entry from `JWT_PREVIOUS_PUBLIC_KEYS_JSON` and delete old private material from the secret store.

During the overlap window, tokens signed with either key verify successfully.

### JWKS

- `GET /auth/jwks.json` — public keys only (for gateways / secondary verifiers).

### Implementation

- `apps/api/app/identity/security/jwt_keys.py` — `JWTKeyRing` / `build_key_ring`
- `apps/api/app/identity/security/token_service.py` — encode/decode with `kid`
- `apps/api/app/api/deps.py` — cached key ring wiring

## Authorization

- Organization-scoped multi-tenancy
- Role-Based Access Control (RBAC)
- Fine-grained permissions per domain (trading, quant, admin)

## Key Principles

- Secrets never leave secret managers (Vault / AWS Secrets Manager / etc.)
- All sensitive operations emit audit events
- Defense in depth: API gateway → service auth → data-layer checks
- Post-quantum readiness path documented (Kyber / Dilithium migration notes)

## Implementation Location

- `apps/api/app/identity/security/token_service.py`
- `apps/api/app/identity/security/jwt_keys.py`
- `packages/security/`
