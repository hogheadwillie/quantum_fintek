# CMMC Alignment Notes

QuantumFintek targets **CMMC Level 2** readiness for potential DoD / defense-adjacent use cases.

## Key Control Families (High-Level Mapping)

| Family | Focus                              | Initial Implementation Notes                  |
|--------|------------------------------------|-----------------------------------------------|
| AC     | Access Control                     | JWT + RBAC + org tenancy                      |
| AU     | Audit & Accountability             | Audit Event model + structured logging        |
| IA     | Identification & Authentication    | MFA hooks, strong password hashing planned    |
| SC     | System & Communications Protection | TLS everywhere, future post-quantum crypto    |
| SI     | System & Information Integrity     | Dependency scanning, container scanning CI    |

## Current Status

- Identity data model defined
- TokenService interface established
- Audit Event entity specified
- Full control evidence collection is future work

This document is a living checklist, not a formal SSP.
