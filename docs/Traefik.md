# Traefik middleware guide (QuantumFintek)

Local overlay: `docker-compose.traefik.yml`  
TLS overlay: `docker-compose.traefik.tls.yml`  
Also see: [TLS.md](./TLS.md), [Development.md](./Development.md)

## Quick start (local)

```bash
cp .env.example .env
# Set a real dashboard password hash:
# htpasswd -nbB admin 'your-password' | sed -e 's/\$/$$/g'
# Put result in TRAEFIK_BASIC_AUTH=...

docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

| URL | Middleware stack |
|-----|------------------|
| http://app.localhost | `qf-rl` → `qf-headers` |
| http://api.localhost | `qf-rl` → `qf-headers` |
| http://localhost/api | `qf-rl` → `api-stripprefix` → `qf-headers` |
| http://traefik.localhost | `dash-auth` (BasicAuth) |
| http://127.0.0.1:8080 | Direct dashboard (loopback only; no BasicAuth on :8080) |

## Middleware inventory

### `qf-rl` — RateLimit

- Default: average 50 req/s, burst 100 (`TRAEFIK_RL_*`)
- Applied to web + API routers
- Source: client IP (direct edge; no trusted `X-Forwarded-For` in local overlay)

### `qf-rl-login` — stricter RateLimit (defined, optional)

- average 5 / burst 10 — attach to a dedicated login router when you split public auth paths

### `qf-headers` — security Headers

- `frameDeny`, `contentTypeNosniff`, `browserXssFilter`
- `referrerPolicy=strict-origin-when-cross-origin`
- Clears `Server` / `X-Powered-By` response headers
- HSTS is **not** set on the local HTTP overlay (use TLS overlay in production)

### `api-stripprefix`

- Strips `/api` for path-based routing so FastAPI routes stay `/quant/...`

### Chains

| Chain | Order |
|-------|--------|
| `qf-web-chain` | rate limit → headers |
| `qf-api-chain` | rate limit → headers |
| `qf-api-path-chain` | rate limit → strip `/api` → headers |

Order follows best practice: cheap limits first, then path rewrite, then response headers.

### `dash-auth` — BasicAuth

- Protects `Host(traefik.localhost)` dashboard router
- `removeHeader=true` so Basic credentials are not forwarded upstream
- **Generate your own hash**; do not rely on any committed default in production

```bash
htpasswd -nbB admin 'your-password' | sed -e 's/\$/$$/g'
# TRAEFIK_BASIC_AUTH=admin:$$2y$$05$$...
```

Note: port `8080` remains bound to loopback without BasicAuth for local debugging. In production, disable insecure API or put it only behind TLS + auth.

## Design rules we follow

1. **Middleware order:** rate limit → auth (when used) → path rewrite → headers → compress
2. **Chains** for reuse instead of duplicating label lists
3. **No ForwardAuth on login/register/health** until a dedicated public router exists
4. **App JWT/RBAC remains authoritative** — edge limits abuse, does not replace FastAPI auth
5. **Pin Traefik** and prefer patched minor versions for auth-header CVEs
6. **Docker socket read-only**; `exposedByDefault=false`

## Production notes

- Use `docker-compose.traefik.tls.yml` for ACME + HTTPS redirect
- Add HSTS (`stsSeconds`) only on TLS entrypoints
- Set entrypoint `forwardedHeaders.trustedIPs` if behind a CDN/LB before relying on IP rate limits
- Consider `underscoreHeadersStrategy=delete` on entrypoints when backends normalize `_` / `-` headers
- Drop published Postgres/Redis host ports and API `:8000` if Traefik is the only ingress

## Optional next steps

- `GET /auth/verify` + ForwardAuth chain for protected API routes
- Dedicated router for `/auth/login` with `qf-rl-login`
- File provider for long middleware definitions outside Compose labels
