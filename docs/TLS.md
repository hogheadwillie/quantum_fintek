# Production Traefik TLS

Use the TLS overlay when DNS points at your host and you want HTTPS via Let's Encrypt.

## Required env

```bash
ACME_EMAIL=ops@yourdomain.com
APP_HOST=app.yourdomain.com
API_HOST=api.yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
CORS_ORIGINS=https://app.yourdomain.com
```

## Start

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.tls.yml up -d --build
```

HTTP on port 80 redirects to HTTPS. Certificates are stored in the `traefik_letsencrypt` volume.

## Notes

- Ensure ports 80/443 are open for the HTTP-01 challenge.
- Do not expose Postgres/Redis publicly in production (remove host port mappings).
- Rotate `SECRET_KEY` and use strong Postgres credentials.
