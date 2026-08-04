# CMMC L2 mapping (subset)

This document tracks how QuantumFintek implements a **subset** of CMMC Level 2 practices. It is not a full certification package.

## Controls in progress

| Control | Practice | Implementation |
|---------|----------|----------------|
| AC.L2-3.1.1 | Limit system access | JWT auth; RBAC (`analyst`/`quant`/`admin`/`owner`) on quant & AI routes |
| AU.L2-3.3.1 | Create audit records | `audit_events` table; register/login/logout writes |
| IA.L2-3.5.1 | Identify users | Email identity; bcrypt hashes; Redis refresh rotation + denylist |
| SC.L2-3.13.1 | Boundary protection | Traefik edge, TLS overlay, rate limits, optional ForwardAuth |

## Machine evidence API

```http
GET /compliance/evidence
Authorization: Bearer <token with admin or owner role>
```

Returns structured evidence pointers for the controls above.

## Gaps (next)

- Full audit export (SIEM sink)
- MFA / step-up auth
- Media protection & key management policy pack
- Formal SSP / POA&M documents
