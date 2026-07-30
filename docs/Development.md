# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (recommended)
- Git

## Local Setup

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
pip install -r apps/api/requirements.txt   # once created
```

### 3. Frontend

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

## Next Milestones

1. Complete JWT TokenService + session store
2. Basic portfolio optimizer in quant-core
3. Anomaly detection stub in ai-intel
4. Docker Compose for local full stack
5. CMMC control evidence collection start
