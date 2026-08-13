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
| `JWT_JWKS_CACHE_MAX_AGE` | HTTP `Cache-Control max-age` for JWKS (default 300s) |
| `JWT_JWKS_STALE_WHILE_REVALIDATE` | `stale-while-revalidate` (default 60s) |

Production requires RS256 via **PEM or key store file**. HS* is rejected.

### JWKS caching strategy

`GET /auth/jwks.json` is the public key distribution endpoint for gateways and secondary verifiers.

| Layer | Behavior |
|-------|----------|
| **In-process** | `KeyRingManager` caches the JWKS JSON + weak ETag after first build |
| **Invalidation** | Any `rotate()` or init bumps `jwks_generation` and clears the cache |
| **ETag** | `W/"jwks-{generation}-{sha256}"`; `If-None-Match` → **304** |
| **Cache-Control** | `public, max-age=…, stale-while-revalidate=…, must-revalidate` |
| **Debug headers** | `X-QF-JWKS-Generation`, `X-QF-JWKS-Active-Kid` |

Guidance:

- Set `max-age` **much lower** than `JWT_ROTATION_INTERVAL_SECONDS` (e.g. 300s vs 24h) so clients pick up new keys quickly after rotation.
- Rely on **ETag** for cheap revalidation; clients should send `If-None-Match`.
- Edge/CDN may cache JWKS; after admin rotate, wait for max-age or purge the path if you need instant global visibility.
- QuantumFintek **API verification does not use JWKS HTTP** — it reads the live key ring in-process. JWKS is for external consumers.

### Automated rotation

1. On startup, `KeyRingManager` loads store / env PEMs / bootstrap.
2. `JWT_AUTO_ROTATE=true` schedules `rotate()` on an interval.
3. Each rotation promotes a new RSA key, keeps previous publics, prunes, persists, **invalidates JWKS cache**.
4. Admin: `POST /admin/jwt/rotate`, `GET /admin/jwt/keys` (includes `jwks_generation` / `jwks_etag`).

**Multi-instance:** share the same key-store volume. Private keys never appear in JWKS.

### Sign / verify

- New tokens: active private key + header `kid`
- Verify: select by `kid`; reject disallowed `alg`
- Unknown `kid` → invalid token

### Implementation

- `apps/api/app/identity/security/jwt_keys.py` — ring model
- `apps/api/app/identity/security/key_rotation.py` — manager, scheduler, store, JWKS cache
- `apps/api/app/identity/security/jwks_cache.py` — ETag helpers
- `apps/api/app/identity/security/token_service.py` — encode/decode
- `apps/api/app/api/routes/auth.py` — JWKS HTTP
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
