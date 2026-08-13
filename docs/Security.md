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
| `JWT_KEY_ID` | Active signing key id when using env PEMs |
| `JWT_PRIVATE_KEY_PEM` / `JWT_PUBLIC_KEY_PEM` | Bootstrap keys (optional if store exists) |
| `JWT_PREVIOUS_PUBLIC_KEYS_JSON` | Manual previous publics (optional; store handles this after first rotate) |
| `JWT_KEY_STORE_PATH` | Persisted key ring JSON (recommended for auto-rotate) |
| `JWT_AUTO_ROTATE` | `true` to enable background rotation |
| `JWT_ROTATION_INTERVAL_SECONDS` | Default `86400` (24h) |
| `JWT_MAX_PREVIOUS_KEYS` | Retired public keys retained for verify (default 2) |
| `JWT_KEY_BITS` | RSA size (default 2048) |
| `JWT_KID_PREFIX` | Generated kid prefix (default `qf-key`) |
| `JWT_AUTO_BOOTSTRAP` | Non-prod: generate RSA if no PEM/store |

Production requires RS256 via **PEM or key store file**. HS* is rejected.

### Automated rotation

1. On startup, `KeyRingManager` loads:
   - `JWT_KEY_STORE_PATH` if present, else
   - env PEMs, else
   - bootstrap RSA (non-prod only when `JWT_AUTO_BOOTSTRAP=true`)
2. When `JWT_AUTO_ROTATE=true`, a background task calls `rotate()` every interval.
3. Each rotation:
   - Generates new RSA key + `kid`
   - Signs new tokens with the new private key
   - Keeps previous **public** keys (strips old private from memory/store)
   - Prunes publics beyond `JWT_MAX_PREVIOUS_KEYS`
   - Atomically rewrites the store file (`chmod 600`)
4. Admin can force rotation: `POST /admin/jwt/rotate` (role `admin`)
5. Status (no secrets): `GET /admin/jwt/keys`
6. Public JWKS updates live: `GET /auth/jwks.json`

**Multi-instance:** each process needs the **same** store volume (or inject the same PEMs). Private keys are not published to Redis. Prefer a shared mounted secret volume or external KMS/Vault in enterprise deployments.

### Manual rotation (still supported)

```bash
./scripts/gen_jwt_rs256_keys.sh qf-key-2
# Set JWT_PREVIOUS_PUBLIC_KEYS_JSON + new JWT_KEY_ID / PEMs, restart
```

Or rely on auto-rotate / admin API when using the key store.

### Sign / verify

- New tokens: active private key + header `kid`
- Verify: select by `kid`; reject disallowed `alg`
- Unknown `kid` → invalid token

### Implementation

- `apps/api/app/identity/security/jwt_keys.py` — ring model
- `apps/api/app/identity/security/key_rotation.py` — manager, scheduler, store
- `apps/api/app/identity/security/token_service.py` — encode/decode
- `apps/api/app/api/routes/admin.py` — rotate / status

## Authorization

- Organization-scoped multi-tenancy
- Role-Based Access Control (RBAC)
- Fine-grained permissions per domain (trading, quant, admin)

## Key Principles

- Secrets never leave secret managers / locked volumes
- All sensitive operations emit audit events (`security.jwt.rotate`)
- Defense in depth: API gateway → service auth → data-layer checks
- Post-quantum readiness path documented (Kyber / Dilithium migration notes)
