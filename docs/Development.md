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

## Next Milestones

1. Wire TokenService to Redis session / denylist store
2. Database models + Alembic migrations
3. Basic portfolio optimizer endpoints
4. Anomaly detection API routes
5. Next.js frontend Dockerfile + compose service
6. CMMC control evidence collection start
