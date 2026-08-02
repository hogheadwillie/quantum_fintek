# QuantumFintek™

Enterprise quantitative finance platform: quant analytics, AI intelligence, JWT/RBAC security, and quantum-ready optimization hooks.

## Status

**v0.5.0-alpha**

- Alembic migrations (identity schema)
- Register / login (bcrypt) + Redis refresh tokens
- RBAC: quant & AI routes require `analyst` (or `admin`)
- Web console: auth, portfolio optimize, risk (VaR/CVaR), anomaly detection
- Traefik local + production TLS overlays

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
# Local HTTP
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build

# Production TLS (see docs/TLS.md)
docker compose -f docker-compose.yml -f docker-compose.traefik.tls.yml up -d --build
```

## Auth & RBAC

1. Register → Login (token includes `user`, `analyst`)
2. `/quant/*` and `/ai/*` require Bearer + analyst/admin role
3. Refresh tokens stored in Redis with rotation

## Migrations

On API startup, Alembic runs `upgrade head`. Manual:

```bash
cd apps/api && alembic upgrade head
```
