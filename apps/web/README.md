# QuantumFintek Web

Next.js enterprise frontend application.

## Planned modules

- Dashboard
- Trading Workspace
- Quant Lab
- AI Intelligence Center
- Administration

## Routing (Traefik + local)

Full details: [`docs/Development.md`](../../docs/Development.md#frontend-routing).

### Recommended local pattern (host-based)

| URL | Service |
|-----|---------|
| http://app.localhost | This Next.js app |
| http://api.localhost | FastAPI backend |

```bash
# Browser-visible API base URL
NEXT_PUBLIC_API_URL=http://api.localhost
```

API `CORS_ORIGINS` must include `http://app.localhost` (and `http://localhost:3000` when using `npm run dev`).

### Path-based alternative (single host)

| URL | Service |
|-----|---------|
| http://localhost/ | Web |
| http://localhost/api | API (prefix stripped by Traefik) |

```bash
NEXT_PUBLIC_API_URL=http://localhost/api
```

### Local UI development (no Docker for web)

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# With Traefik overlay running:
# NEXT_PUBLIC_API_URL=http://api.localhost npm run dev
```

Open http://localhost:3000.

### Compose + Traefik

When the `web` service and Dockerfile exist:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up --build
```

Traefik labels for `web` are prepared (commented) in `docker-compose.traefik.yml`.
