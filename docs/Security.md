# Security Architecture

## Authentication

- **Access tokens**: Short-lived JWT (15–30 min) signed with RS256 or ES256
- **Refresh tokens**: Opaque, stored server-side, rotated on every use
- **Session binding**: Optional IP / user-agent fingerprint checks
- **Revocation**: Immediate via denylist / session store

## Authorization

- Organization-scoped multi-tenancy
- Role-Based Access Control (RBAC)
- Fine-grained permissions per domain (trading, quant, admin)

## Key Principles

- Secrets never leave secret managers (Vault / AWS Secrets Manager / etc.)
- All sensitive operations emit audit events
- Defense in depth: API gateway → service auth → data-layer checks
- Post-quantum readiness path documented (Kyber / Dilithium migration notes)

## Implementation Location

- `apps/api/app/identity/security/token_service.py`
- Future: `packages/security/`
