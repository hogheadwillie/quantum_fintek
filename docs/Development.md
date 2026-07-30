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

## Frontend routing

The Next.js app (`apps/web`) is planned to sit behind the same Traefik entrypoint as the API. Use **one** of the patterns below; do not mix them in production without careful cookie/CORS design.

### Pattern A — Host-based (recommended for local)

| Host | Backend |
|------|---------|
| `http://app.localhost` | Next.js web (`web:3000`) |
| `http://api.localhost` | FastAPI (`api:8000`) |

**Frontend env (browser-visible):**

```bash
NEXT_PUBLIC_API_URL=http://api.localhost
```

**CORS on API** must allow the web origin:

```bash
CORS_ORIGINS=http://app.localhost,http://localhost:3000
```

Traefik labels (already sketched in `docker-compose.traefik.yml` for the future `web` service):

```yaml
labels:
  - traefik.enable=true
  - traefik.docker.network=quantum-net
  - traefik.http.routers.web.rule=Host(`app.localhost`)
  - traefik.http.routers.web.entrypoints=web
  - traefik.http.services.web-svc.loadbalancer.server.port=3000
```

### Pattern B — Path-based (single host)

| Path | Backend |
|------|---------|
| `http://localhost/` | Next.js web |
| `http://localhost/api` | FastAPI (strip `/api` prefix) |

**Frontend env:**

```bash
NEXT_PUBLIC_API_URL=http://localhost/api
```

API PathPrefix route + strip middleware is already active in the Traefik overlay. Web would use a low-priority catch-all Host rule or `PathPrefix(`/`)` with priority lower than `/api`.

Priority tip in Traefik v3:

```yaml
- traefik.http.routers.api-path.priority=100
- traefik.http.routers.web.priority=1
```

### Local frontend without Docker

While iterating on UI only:

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# or with Traefik up:
# NEXT_PUBLIC_API_URL=http://api.localhost npm run dev
```

Open http://localhost:3000. Next.js talks to the API using `NEXT_PUBLIC_API_URL`.

### Enabling the web service in Compose

1. Uncomment the `web` service in `docker-compose.yml` (and add `apps/web/Dockerfile` when ready).
2. Ensure Traefik labels for `web` are present in `docker-compose.traefik.yml`.
3. Set:

```bash
NEXT_PUBLIC_API_URL=http://api.localhost
CORS_ORIGINS=http://app.localhost,http://localhost:3000
```

4. Start with the Traefik overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

### Production routing sketch

| Public URL | Service |
|------------|---------|
| `https://app.quantumfintek.example` | web |
| `https://api.quantumfintek.example` | api |

Use Traefik `websecure` entrypoint + Let's Encrypt cert resolver. Prefer host-based split over path-based for clearer TLS certs, cookies, and CORS.

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
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
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
| web       | planned                | 3000  | Next.js frontend           |

## Next Milestones

1. Wire TokenService to Redis session / denylist store
2. Database models + Alembic migrations
3. Basic portfolio optimizer endpoints
4. Anomaly detection API routes
5. Next.js frontend Dockerfile + compose service
6. Production Traefik TLS (ACME) profile
7. CMMC control evidence collection start
