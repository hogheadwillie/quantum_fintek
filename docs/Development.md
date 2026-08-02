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

## Traefik

```bash
# Base proxy + rate limit + headers + dashboard BasicAuth
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build

# + ForwardAuth on protected API routes
docker compose \
  -f docker-compose.yml \
  -f docker-compose.traefik.yml \
  -f docker-compose.traefik.auth.yml \
  up --build
```

Details: [Traefik.md](./Traefik.md) · TLS: [TLS.md](./TLS.md)

## Frontend routing

```bash
NEXT_PUBLIC_API_URL=http://api.localhost
CORS_ORIGINS=http://app.localhost,http://localhost:3000
```

```bash
cd apps/web && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## API examples

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.com","username":"analyst","password":"changeme123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@example.com","password":"changeme123"}' | jq -r .access_token)

curl -s -X POST http://localhost:8000/quant/optimize \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"expected_returns":[0.05,0.07,0.06],"covariance":[[0.01,0.002,0.001],[0.002,0.015,0.003],[0.001,0.003,0.012]]}'

# ForwardAuth probe (when auth overlay is up)
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  http://api.localhost/auth/verify
```

## Repository layout

- `apps/api` — FastAPI
- `apps/web` — Next.js
- `packages/*` — shared libraries
- `docs/` — architecture, security, Traefik, TLS

## Status

v0.5.x — Alembic, JWT/RBAC, web auth UI, Traefik TLS + middleware + ForwardAuth
