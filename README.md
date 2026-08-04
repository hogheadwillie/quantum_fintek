# QuantumFintek™

Enterprise quantitative finance platform: quant analytics, AI intelligence, JWT/RBAC security, quantum-ready optimization, and CMMC-aligned controls.

## Status

**v0.6.0-alpha**

- Alembic migrations + audit trail on auth events
- Org + membership created on register
- RBAC on quant / AI / compliance routes
- Web console with visual quant & anomaly panels
- Traefik: rate limits, headers, ForwardAuth, TLS overlay
- GitHub Actions CI

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
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
docker compose -f docker-compose.yml -f docker-compose.traefik.yml -f docker-compose.traefik.auth.yml up --build
docker compose -f docker-compose.yml -f docker-compose.traefik.tls.yml up -d --build
```

## Auth

1. `POST /auth/register` → creates user + default org (owner)
2. `POST /auth/login` → JWT with roles + org_id
3. Bearer required on `/quant/*`, `/ai/*`, `/compliance/*`, `/auth/me`
