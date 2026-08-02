# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (recommended)
- Git

## Local Setup (Docker — recommended)

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Swagger | http://localhost:8000/docs |
| Web | http://localhost:3000 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

```bash
docker compose logs -f api
docker compose down -v
```

## Traefik reverse proxy (optional)

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

| URL | Target | Middleware |
|-----|--------|------------|
| http://app.localhost | Web | rate limit + security headers |
| http://api.localhost | API | rate limit + security headers |
| http://localhost/api | API | rate limit + strip `/api` + headers |
| http://traefik.localhost | Dashboard | BasicAuth |
| http://127.0.0.1:8080 | Dashboard | loopback only |

Set dashboard credentials in `.env`:

```bash
htpasswd -nbB admin 'your-password' | sed -e 's/\$/$$/g'
# TRAEFIK_BASIC_AUTH=admin:$$2y$$05$$...
```

Full middleware notes: [Traefik.md](./Traefik.md). Production TLS: [TLS.md](./TLS.md).

## Frontend routing

**Host-based (recommended)**

```bash
NEXT_PUBLIC_API_URL=http://api.localhost
CORS_ORIGINS=http://app.localhost,http://localhost:3000
```

**Path-based**

```bash
NEXT_PUBLIC_API_URL=http://localhost/api
```

Local UI without Docker web container:

```bash
cd apps/web && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## API examples

```bash
# Register + login (preferred)
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.com","username":"analyst","password":"changeme123"}'

curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.com","password":"changeme123"}'

# Portfolio optimize (Bearer required)
curl -s -X POST http://localhost:8000/quant/optimize \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"expected_returns":[0.05,0.07,0.06],"covariance":[[0.01,0.002,0.001],[0.002,0.015,0.003],[0.001,0.003,0.012]]}'
```

## Repository layout

- `apps/api` — FastAPI
- `apps/web` — Next.js
- `packages/quant-core`, `packages/ai-intel` — shared libraries
- `docs/` — architecture, security, CMMC, Traefik
- `infrastructure/` — k8s / terraform stubs

## Status

v0.5.x — Alembic, JWT/RBAC, web auth UI, Traefik TLS + middleware hardening
