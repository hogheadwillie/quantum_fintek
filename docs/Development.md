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

| URL | Target |
|-----|--------|
| http://app.localhost | Web |
| http://api.localhost | API |
| http://localhost/api | API (PathPrefix + strip) |
| http://localhost:8080 | Traefik dashboard (loopback) |

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
# Tokens (refresh stored in Redis)
curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"subject":"demo-user","roles":["analyst"]}'

# Portfolio optimize
curl -s -X POST http://localhost:8000/quant/optimize \
  -H 'Content-Type: application/json' \
  -d '{"expected_returns":[0.05,0.07,0.06],"covariance":[[0.01,0.002,0.001],[0.002,0.015,0.003],[0.001,0.003,0.012]]}'
```

## Repository layout

- `apps/api` — FastAPI
- `apps/web` — Next.js
- `packages/quant-core`, `packages/ai-intel` — shared libraries
- `docs/` — architecture, security, CMMC
- `infrastructure/` — k8s / terraform stubs

## Next milestones

1. Alembic migrations + wire User model to auth
2. Password hashing + real login flow
3. Protect quant/AI routes with JWT dependency
4. Expand web dashboard (charts, auth UI)
5. Production Traefik TLS (ACME) profile
6. CMMC evidence collection automation
