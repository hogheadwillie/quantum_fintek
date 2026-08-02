# QuantumFintek™

Enterprise quantitative finance platform: quant analytics, AI intelligence, JWT/RBAC security, and quantum-ready optimization hooks.

## Status

**v0.5.x**

- Alembic migrations (identity schema)
- Register / login (bcrypt) + Redis refresh tokens
- RBAC on quant & AI routes
- Web console with auth + quant/AI panels
- Traefik: rate limits, security headers, dashboard BasicAuth, **ForwardAuth** (`/auth/verify`)

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| Docs | http://localhost:8000/docs |

## Traefik

```bash
# Local proxy
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build

# + ForwardAuth (edge JWT gate on protected routes)
docker compose -f docker-compose.yml -f docker-compose.traefik.yml -f docker-compose.traefik.auth.yml up --build

# Production TLS
docker compose -f docker-compose.yml -f docker-compose.traefik.tls.yml up -d --build
```

See [`docs/Traefik.md`](docs/Traefik.md).

## Auth

1. `POST /auth/register` → `POST /auth/login`
2. Bearer token on `/quant/*`, `/ai/*`, `/auth/me`
3. `GET /auth/verify` for Traefik ForwardAuth (returns `X-QF-*` headers)
4. Refresh tokens in Redis with rotation
