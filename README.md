# QuantumFintek™

Enterprise quantitative finance platform: quant analytics, AI intelligence, JWT/RBAC security, quantum-ready optimization, and CMMC-aligned controls.

## Status

**v0.8.0-alpha**

- **IBM Z-series / z/OS integration** (`packages/zos-bridge` + `/zos` API router)
  - EBCDIC ↔ UTF-8 transcoding: 11 code pages (IBM-037, -1047, -1140, -500, …)
  - MVS dataset record-format parser/builder: F, FB, V, VB, U
  - RACF access control model: user profiles, group ACEs, permission hierarchy
  - MQI-compatible MQ bridge: put/get/browse/commit, MQMD envelope, EBCDIC payloads
  - JCL builder: JOB card, EXEC steps, DD statements — standards-compliant z/OS 2.5+ JCL
  - LPAR connection model: LPARConfig, z/OSMF REST client stub, live metrics simulation
- Web UI `/zos` page: sysplex health + LPAR metrics, JCL job monitor, dataset browser, EBCDIC transcoder, MQ bridge panel
- `docs/ZOS.md`: full integration guide, code pages, RACF, MQ production migration path
- CI: zos-bridge included in unit tests + pyright

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
