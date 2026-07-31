# QuantumFintek™

Enterprise quantitative finance platform combining quantitative analytics, trading infrastructure, AI intelligence, quantum-ready optimization, and enterprise security.

## Status

**v0.4.0-alpha** — register/login, JWT-protected quant/AI, web auth UI

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

## Auth flow

1. `POST /auth/register` — create user (bcrypt password)
2. `POST /auth/login` — access + refresh JWT (refresh stored in Redis)
3. `GET /auth/me` — current user (Bearer)
4. `POST /quant/*` and `POST /ai/*` require Bearer token

## Traefik (optional)

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

- http://app.localhost → web
- http://api.localhost → api
