# QuantumFintek™

Enterprise quantitative finance platform: quant analytics, AI intelligence, JWT/RBAC security, quantum-ready optimization, and CMMC-aligned controls.

## Status

**v0.7.0-alpha**

- Trading domain: order management (market/limit/stop), positions aggregation, simulated market data
- Live WebSocket market data stream with GBM tick simulation
- Org management: create orgs, invite members, role management
- Admin console UI: audit log viewer + user management table
- Compliance UI: CMMC L2 evidence viewer with coverage progress
- Sidebar updated with Trading, Compliance, and Admin Console (admin-role-gated)
- `packages/security` promoted to a real shared library (JWT helpers, password hashing)
- Alembic migration 0002: `orders` table
- CI extended: tsc typecheck + pyright on packages

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
3. Bearer required on `/quant/*`, `/ai/*`, `/trading/*`, `/compliance/*`, `/auth/me`

## Trading

- `POST /trading/orders` — place market / limit / stop orders
- `GET /trading/orders` — list own orders
- `DELETE /trading/orders/{id}` — cancel pending order
- `GET /trading/positions` — aggregated positions from filled orders
- `GET /trading/market-data?symbols=AAPL,MSFT` — simulated quotes
- `WS /ws/market-data?symbols=AAPL,MSFT&interval_ms=1000` — live stream

## Org Management

- `GET /orgs` — list my orgs
- `POST /orgs` — create org
- `GET /orgs/{id}` — detail + members
- `POST /orgs/{id}/members` — invite by email
- `PATCH /orgs/{id}/members/{uid}` — update role
- `DELETE /orgs/{id}/members/{uid}` — remove member
