# QuantumFintek API

FastAPI backend for the QuantumFintek institutional trading platform.

## Current foundation

- Typed environment configuration
- Versioned API routing
- Liveness and readiness endpoints
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

## Validation

```bash
ruff check .
ruff format --check .
pytest

docker build -t quantum-fintek-api .
docker run --rm -p 8000:8000 quantum-fintek-api
```

## Planned modules

- Authentication and identity
- Market data
- Order and execution management
- Portfolio and risk management
- Quant analytics
- AI services
