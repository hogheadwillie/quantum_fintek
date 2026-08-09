# QuantumFintek Architecture — v0.8.0

## Core Domains

1. **Trading Platform**
   Order management, market data ingestion, execution adapters, risk gates.

6. **IBM Z-series / z/OS Integration** (`packages/zos-bridge`)
   EBCDIC ↔ UTF-8 transcoding (11 code pages), MVS dataset record-format parsing (F/FB/V/VB/U), RACF access control simulation, MQI-compatible message envelope, JCL builder, LPAR/z/OSMF connection model.

2. **Quantitative Engine** (`packages/quant-core`)  
   Portfolio optimization, risk models (VaR, CVaR), factor models, backtesting, quantum-ready QUBO / VQE interfaces.

3. **AI Intelligence** (`packages/ai-intel`)  
   Anomaly detection, sentiment, predictive signals, LLM-augmented research assistants (Grok / xAI integration path).

4. **Enterprise Platform**  
   Multi-tenant organizations, RBAC, billing, audit, admin console (Next.js).

5. **Security Infrastructure**  
   JWT access + rotating refresh tokens, session binding, MFA hooks, audit events, post-quantum readiness notes, CMMC L2 control mapping.

## High-Level Component Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Next.js Web    │────▶│  FastAPI Gateway │────▶│  Identity / JWT │
│  (apps/web)     │     │  (apps/api)      │     │  + RBAC         │
└─────────────────┘     └───────────┬──────┘     └────────────────┘
                                    │
              ┌──────────┬──────────┼──────────┬──────────┐
              ▼          ▼          ▼          ▼          ▼
         quant-core  ai-intel   trading     orgs     zos-bridge
         (packages) (packages)  (apps)    (apps)    (packages)
                                                        │
                                             ┌──────────▼──────────┐
                                             │  IBM Z LPAR          │
                                             │  z/OS 2.5/3.1        │
                                             │  JES2 · MQ · RACF    │
                                             └─────────────────────┘
```

## Deployment Model

- Containerized services (Docker)
- Orchestrated via Kubernetes
- Infrastructure managed with Terraform / GitOps
- Observability: structured logging, metrics, tracing (OpenTelemetry target)

## Design Principles

- **Security first** — least privilege, defense in depth, auditability
- **Observable systems** — every critical path emits metrics & traces
- **Modular services** — clear bounded contexts, shared packages only for pure logic
- **Testable components** — unit + integration + contract tests from day one
- **Enterprise scalability** — horizontal scaling, multi-tenant isolation

## Technology Stack (Target)

| Layer          | Choice                          |
|----------------|---------------------------------|
| API            | FastAPI + Pydantic v2           |
| Auth           | JWT (access) + opaque refresh   |
| Frontend       | Next.js (App Router)            |
| Quant          | NumPy / SciPy / pandas + Qiskit |
| AI             | scikit-learn / PyTorch + Grok API |
| Data           | PostgreSQL + Timescale / Redis  |
| Mainframe      | IBM z/OS 2.5/3.1 via z/OSMF REST + pymqi |
| Orchestration  | Kubernetes + Helm               |
| IaC            | Terraform                       |
