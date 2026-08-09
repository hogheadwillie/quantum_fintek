"""IBM z/OS Integration

QuantumFintek connects to IBM Z-series mainframes via the **zos-bridge** package
(`packages/zos-bridge`) and the `/zos` API router.

## Architecture Overview

```
┌─────────────────────┐    REST + WS     ┌──────────────────────┐
│   Next.js Web       │ ─────────────▶   │  FastAPI /zos router │
│   /zos page         │                  │  (apps/api)          │
└─────────────────────┘                  └──────────┬───────────┘
                                                    │ zos-bridge
                                         ┌──────────▼───────────┐
                                         │  zos_bridge package  │
                                         │  codec / dataset /   │
                                         │  jcl / mq / racf /   │
                                         │  lpar                │
                                         └──────────┬───────────┘
                                                    │ z/OSMF REST (prod)
                                         ┌──────────▼───────────┐
                                         │  IBM Z LPAR          │
                                         │  (z/OS 2.5 / 3.1)    │
                                         │  JES2  MQ  RACF      │
                                         └──────────────────────┘
```

## LPAR Configuration

Configured in `apps/api/app/api/routes/zos.py` under `_LPAR_CONFIGS`.
In production, move to `.env` or a secret manager:

```bash
ZOS_LPAR_A_HOST=zosmf-a.example.com
ZOS_LPAR_A_PORT=443
ZOS_LPAR_A_USER=QFTSVC
ZOS_LPAR_A_PASSWORD=<vault reference>
ZOS_SYSPLEX=FINPLEX
```

Add to `Settings` in `apps/api/app/core/config.py`:

```python
zos_lpar_a_host: str = "zosmf-a.example.com"
zos_lpar_a_port: int = 443
zos_lpar_a_user: str = ""
zos_lpar_a_password: str = ""
zos_sysplex: str = "FINPLEX"
```

## Code Pages

| Code Page | Python Name | Use Case |
|-----------|-------------|----------|
| IBM-037   | `cp037`     | US English — classic COBOL / batch (default) |
| IBM-1047  | `cp1047`    | UNIX System Services (USS) / USS shell |
| IBM-1140  | `cp1140`    | US English + Euro € sign |
| IBM-500   | `cp500`     | International EBCDIC |
| IBM-273   | `cp273`     | German EBCDIC |
| IBM-285   | `cp285`     | UK English EBCDIC |

## Dataset Record Formats

| RECFM | Description | Notes |
|-------|-------------|-------|
| `FB`  | Fixed Blocked | Most common; LRECL=80 for JCL/COBOL source |
| `F`   | Fixed Unblocked | Same as FB, one record per block |
| `VB`  | Variable Blocked | 4-byte RDW prefix per record |
| `V`   | Variable Unblocked | As VB without blocking |
| `U`   | Undefined | Load libraries, object decks |

Upload/download via:
- `POST /zos/datasets/upload` — send UTF-8 lines, receive base64 EBCDIC
- `POST /zos/datasets/download` — receive decoded UTF-8 lines from a DSN

## JCL Job Submission

```bash
# Submit a single-step job
curl -X POST http://localhost:8000/zos/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_name": "QFJOB01",
    "lpar": "SYSA",
    "program": "IEFBR14",
    "parm": "REPORT=MONTHLY"
  }'
```

To submit raw JCL text:

```bash
curl -X POST http://localhost:8000/zos/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"job_name":"QFJOB02","lpar":"SYSA","jcl":"//QFJOB02 JOB ..."}'
```

JCL Builder Python API:

```python
from zos_bridge.jcl import JCLBuilder, DDStatement

jcl = (
    JCLBuilder("PAYREPT", account="QFINTEK")
    .notify("OPS01")
    .comment("Monthly payroll COBOL report")
    .step("COBRUN", program="COBPAY01", parm="MONTH=JAN,YEAR=2025")
    .dd(dd_name="SYSIN",    dsn="QFINTEK.PAYROLL.MASTER", disp="SHR")
    .dd(dd_name="SYSPRINT", sysout="*")
    .dd(dd_name="SYSOUT",   sysout="*")
    .end_step()
    .render()
)
```

## MQ Bridge

### Put a message

```bash
curl -X POST http://localhost:8000/zos/mqbridge/put \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"queue_name":"QFINTEK.ORDERS.LOCAL","payload":"BUY 100 AAPL @ MKT"}'
```

### Get a message

```bash
curl "http://localhost:8000/zos/mqbridge/get?queue_name=QFINTEK.ORDERS.LOCAL" \
  -H "Authorization: Bearer $TOKEN"
```

### Production MQ setup

Replace the in-memory `MQBridgeAdapter` with **pymqi**:

```python
import pymqi

qmgr = pymqi.connect("QM_PROD", "SYSTEM.DEF.SVRCONN", "zosmf-a.example.com(1414)")
q = pymqi.Queue(qmgr, "QFINTEK.ORDERS.LOCAL")
q.put(payload.encode("cp037"))
msg = q.get()
qmgr.disconnect()
```

## RACF Access Control

The `/zos/racf/check` endpoint simulates RACF permission resolution:

```bash
curl -X POST http://localhost:8000/zos/racf/check \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "userid": "JDOE",
    "groups": ["FINGRP"],
    "resource_name": "QFINTEK.PAYROLL.MASTER",
    "resource_class": "DATASET"
  }'
```

**Permission hierarchy** (highest wins):

1. `SPECIAL` attribute → `ALTER`
2. Explicit USER ACE
3. Best matching GROUP ACE
4. UACC (Universal Access)
5. Default: `NONE`

## EBCDIC ↔ UTF-8 Transcoding

```bash
# Encode UTF-8 to EBCDIC (IBM-037, 80-byte fixed records)
curl -X POST http://localhost:8000/zos/transcode \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text":"HELLO WORLD","code_page":"cp037","record_length":80,"include_hex_dump":true}'

# Decode back
curl -X POST http://localhost:8000/zos/transcode/decode \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"ebcdic_b64":"<base64>","code_page":"cp037","record_length":80}'
```

## Security Controls

| Control | Implementation |
|---------|----------------|
| Authentication | JWT Bearer token — all `/zos/*` routes require `analyst` role minimum |
| Authorisation | RACF simulation via `zos_bridge.racf`; production uses real RACF passtickets |
| Transport | z/OSMF REST over TLS 1.2+; `tls_verify=True` enforced in `LPARConfig` |
| Credential storage | `username`/`password` never in source — use environment secrets or HashiCorp Vault |
| Audit | All JCL submissions and MQ operations emit `zos.*` audit events |

## Mainframe Hardware Reference

| Model | Name | Max LPAR Memory |
|-------|------|----------------|
| 3931  | IBM z16 | 40 TB |
| 3906  | IBM z15 | 16 TB |
| 3907  | IBM z14 | 32 TB |

## z/OS REST API Reference (Production)

- z/OSMF Jobs REST API: `POST /zosmf/restjobs/jobs`
- z/OSMF Data Sets: `GET /zosmf/restfiles/ds/{dsn}`
- z/OS Connect EE: REST → CICS / IMS transaction gateway
"""
