# QuantumFintek™

Enterprise quantitative finance platform combining:

- Quantitative analytics
- Trading infrastructure
- AI financial intelligence
- Quantum-ready optimization research
- Enterprise security architecture (JWT + CMMC-aligned controls)

## Development Status

**Current milestone: v0.2.0-alpha — Foundation + Core Domains Scaffolded**

Previous: v0.1.0-alpha — Repository Foundation

## Repository Structure

```
apps/
  api/                 # FastAPI backend
  web/                 # Next.js frontend
packages/
  quant-core/          # Shared quantitative engines
  ai-intel/            # AI financial intelligence
  security/            # Shared auth & crypto utilities
infrastructure/
  k8s/                 # Kubernetes manifests
  terraform/           # Infrastructure as Code stubs
docs/
  Architecture.md
  Development.md
  Security.md
  CMMC.md
scripts/
tests/
```

## Quick Start

See [`docs/Development.md`](docs/Development.md) for local setup.

## Core Domains

| Domain                | Location                          | Status      |
|-----------------------|-----------------------------------|-------------|
| Security / Identity   | `apps/api/app/identity/`          | Scaffolded  |
| Quantitative Engine   | `packages/quant-core/`            | Scaffolded  |
| AI Intelligence       | `packages/ai-intel/`              | Scaffolded  |
| Trading Platform      | `apps/api/app/trading/`           | Planned     |
| Enterprise Platform   | `apps/web/`                       | Planned     |

## Design Principles

- Security first (JWT, refresh rotation, CMMC L2 alignment)
- Observable systems
- Modular services
- Testable components
- Enterprise scalability (Kubernetes-ready)
