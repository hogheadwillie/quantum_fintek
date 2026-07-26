# QuantumFintek API

FastAPI backend for the QuantumFintek institutional trading platform.

## Current foundation

- Typed environment configuration
- Versioned API routing
- Liveness and readiness endpoints
- Tenant-scoped identity models and authentication
- Tenant-scoped identity persistence with Alembic migrations
- Argon2 password hashing and JWT bearer tokens
- Bearer-token login and current-user endpoints
- OpenAPI documentation outside production
- Pytest coverage enforcement
- Ruff linting and formatting
- Non-root production container
- GitHub Actions quality and container checks

## Local development

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The API is available at `http://localhost:8000`.

- OpenAPI UI: `/docs`
- Liveness: `/api/v1/health`
- Readiness: `/api/v1/ready`
- Login: `POST /api/v1/identity/login`
- Current user: `GET /api/v1/identity/me`

## Database migrations

Set `QF_DATABASE_URL` in `.env`, then run:

```bash
alembic upgrade head
alembic current
```

Create future schema revisions with:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Review every generated migration before committing it. Use `alembic downgrade base` to reset a local development database.

## Validation

```bash
ruff check .
ruff format --check .
mypy
pytest

docker build -t quantum-fintek-api .
docker run --rm -p 8000:8000 quantum-fintek-api
```

## Planned modules

- Refresh token rotation and session revocation
- Role-based access control
- Market data
- Order and execution management
- Portfolio and risk management
- Quant analytics
- AI services
