# QuantumFintek™

Enterprise quantitative finance platform combining:

- Quantitative analytics
- Trading infrastructure
- AI financial intelligence
- Quantum-ready optimization research
- Enterprise security architecture (JWT + CMMC-aligned controls)

## Development Status

**Current milestone: v0.3.0-alpha — API routes + web console + Redis sessions**

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Web | http://localhost:3000 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

With Traefik:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

| Host | Target |
|------|--------|
| http://app.localhost | Web |
| http://api.localhost | API |

## Core endpoints

- `POST /auth/token` — issue JWT access + refresh (Redis-backed refresh)
- `POST /auth/refresh` — rotate refresh token
- `POST /quant/optimize` — mean-variance weights
- `POST /quant/risk` — VaR / CVaR / volatility
- `POST /quant/qubo` — quantum-ready QUBO payload
- `POST /ai/anomaly` — Isolation Forest anomaly detection

See [`docs/Development.md`](docs/Development.md) for full setup and frontend routing.
