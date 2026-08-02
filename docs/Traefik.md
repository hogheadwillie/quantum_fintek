# Traefik middleware guide (QuantumFintek)

| Overlay | File |
|---------|------|
| Local HTTP | `docker-compose.traefik.yml` |
| ForwardAuth | `docker-compose.traefik.auth.yml` |
| Production TLS | `docker-compose.traefik.tls.yml` |

Also see: [TLS.md](./TLS.md), [Development.md](./Development.md)

## Quick start (local)

```bash
cp .env.example .env
# Dashboard BasicAuth:
# htpasswd -nbB admin 'your-password' | sed -e 's/\$/$$/g'

docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

### With ForwardAuth

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.traefik.yml \
  -f docker-compose.traefik.auth.yml \
  up --build
```

| URL | Middleware stack |
|-----|------------------|
| http://app.localhost | `qf-rl` → `qf-headers` |
| http://api.localhost/auth/* | public: rate limit + headers |
| http://api.localhost/quant/* | **ForwardAuth** + rate limit + headers |
| http://localhost/api/... | same split after strip |
| http://traefik.localhost | BasicAuth dashboard |

## ForwardAuth

### Verify endpoint

`GET /auth/verify` (FastAPI):

- Requires `Authorization: Bearer <access_token>`
- Validates JWT + Redis denylist via existing `TokenService`
- **200** empty body + headers:
  - `X-QF-User-Id`
  - `X-QF-Roles` (comma-separated)
  - `X-QF-Org-Id` (optional)
- **401** if missing/invalid

### Traefik middleware settings

```text
address              = http://api:8000/auth/verify
authRequestHeaders   = Authorization          # allowlist only
authResponseHeaders  = X-QF-User-Id,X-QF-Roles,X-QF-Org-Id
trustForwardHeader   = false
maxResponseBodySize  = 1024
```

### Public vs protected routers

| Class | Paths | ForwardAuth |
|-------|-------|-------------|
| Public | `/auth/*`, `/health`, `/`, `/docs`, `/openapi.json`, `/redoc` | No |
| Protected | everything else on API host (e.g. `/quant/*`, `/ai/*`, `/auth/me`) | Yes |

Note: `/auth/me` and `/auth/verify` are under `/auth` so they match the **public** Traefik path prefix. `/auth/me` still requires JWT **inside** FastAPI. `/auth/verify` is only called by Traefik’s ForwardAuth subrequest.

If you need edge auth on `/auth/me`, split routers further (e.g. public only `PathPrefix(/auth/login)` + register + refresh).

### Header trust rules

1. Clients must not be trusted for `X-QF-*` — only the verify endpoint sets them after JWT validation.
2. FastAPI **still** validates Bearer JWT on protected routes (RBAC unchanged).
3. Treat `X-QF-*` as optional convenience headers, not sole authentication.
4. Keep Traefik image patched for ForwardAuth header CVEs.

### Manual test

```bash
# Login
TOKEN=$(curl -s -X POST http://api.localhost/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.com","password":"changeme123"}' | jq -r .access_token)

# Edge-protected quant call
curl -s -X POST http://api.localhost/quant/optimize \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"expected_returns":[0.05,0.07],"covariance":[[0.01,0.0],[0.0,0.02]]}'

# Without token → 401 from ForwardAuth
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://api.localhost/quant/optimize
```

## Middleware inventory (base overlay)

### `qf-rl` — RateLimit

- Default: average 50 req/s, burst 100 (`TRAEFIK_RL_*`)

### `qf-headers` — security Headers

- frame deny, nosniff, XSS filter, referrer policy; strip Server / X-Powered-By

### `api-stripprefix`

- Strips `/api` for path-based routing

### Chains

| Chain | Order |
|-------|--------|
| `qf-web-chain` | rate limit → headers |
| `qf-api-public-chain` | rate limit → headers |
| `qf-api-protected-chain` | rate limit → **ForwardAuth** → headers |
| `qf-api-path-*-chain` | same with strip for `/api` |

### `dash-auth` — BasicAuth

```bash
htpasswd -nbB admin 'your-password' | sed -e 's/\$/$$/g'
# TRAEFIK_BASIC_AUTH=admin:$$2y$$05$$...
```

## Design rules

1. Rate limit before auth; headers after decisions
2. Chains for reuse
3. No ForwardAuth on login/register/health
4. App JWT/RBAC remains authoritative
5. Pin Traefik; docker.sock read-only; `exposedByDefault=false`

## Production notes

- Combine with `docker-compose.traefik.tls.yml` for HTTPS
- Add HSTS only on TLS entrypoints
- Set `forwardedHeaders.trustedIPs` behind CDN/LB
- Consider `underscoreHeadersStrategy=delete` on entrypoints
