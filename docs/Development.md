# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (recommended)
- Git

## Local Setup (Docker — recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start the full stack (API + Postgres + Redis)
docker compose up --build

# API will be available at http://localhost:8000
# Health check: http://localhost:8000/health
# Postgres: localhost:5432
# Redis: localhost:6379
```

Useful commands:

```bash
docker compose up -d          # detached
docker compose logs -f api    # follow API logs
docker compose down           # stop
docker compose down -v        # stop + remove volumes
```

## Traefik reverse proxy (optional overlay)

Traefik is provided as an **opt-in** compose overlay so the default stack stays light.

```bash
# Start core stack + Traefik
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

| URL | Target |
|-----|--------|
| http://api.localhost | API via Traefik (Host rule) |
| http://localhost/api | API via Traefik (PathPrefix + strip) |
| http://localhost:8000 | API direct (still published) |
| http://localhost:8080 | Traefik dashboard (loopback only) |
| http://traefik.localhost | Dashboard via Traefik Host rule |

Notes:

- `*.localhost` resolves to `127.0.0.1` on modern OS setups (no hosts file edit needed).
- Postgres and Redis are **not** exposed through Traefik.
- Docker socket is mounted **read-only**.
- `exposedByDefault=false` — only labeled services are routed.
- For production TLS, extend the overlay with `websecure` entrypoint + ACME cert resolver (not enabled in local overlay).

Stop the Traefik-enabled stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml down
```

## Local Setup (without Docker)

### 1. Clone

```bash
git clone https://github.com/hogheadwillie/quantum_fintek.git
cd quantum_fintek
```

### 2. Python environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e packages/quant-core
pip install -e packages/ai-intel
pip install -r apps/api/requirements.txt
```

Or use the bootstrap script:

```bash
bash scripts/bootstrap.sh
```

### 3. Frontend (when implemented)

```bash
cd apps/web
npm install
npm run dev
```

### 4. API

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
```

## Monorepo Layout

- `apps/*` — deployable applications
- `packages/*` — pure Python libraries (quant, AI, security helpers)
- `infrastructure/` — K8s manifests & Terraform
- `docs/` — architecture, security, CMMC mapping
- `scripts/` — automation & CI helpers
- `tests/` — cross-cutting integration tests

## Coding Standards

- Type hints everywhere
- Pydantic models for all external I/O
- No secrets in code; use environment variables / secret managers
- Every new module ships with unit tests
- Prefer composition over inheritance

## Docker Services

| Service   | Image / Build          | Port  | Purpose                    |
|-----------|------------------------|-------|----------------------------|
| api       | `apps/api/Dockerfile`  | 8000  | FastAPI backend            |
| postgres  | postgres:16-alpine     | 5432  | Primary database           |
| redis     | redis:7-alpine         | 6379  | Cache / sessions / queues  |
| traefik   | traefik:v3.3 (overlay) | 80 / 8080 | Optional reverse proxy  |

## Next Milestones

1. Wire TokenService to Redis session / denylist store
2. Database models + Alembic migrations
3. Basic portfolio optimizer endpoints
4. Anomaly detection API routes
5. Next.js frontend Dockerfile + compose service
6. Production Traefik TLS (ACME) profile
7. CMMC control evidence collection start
