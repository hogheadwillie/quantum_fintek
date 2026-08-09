"""IBM z/OS integration API routes.

Endpoints:
  GET  /zos/health              — LPAR connectivity + metrics
  GET  /zos/lpars               — list configured LPARs
  POST /zos/transcode           — EBCDIC ↔ UTF-8 transcoding
  GET  /zos/datasets            — list dataset catalogue stubs
  POST /zos/datasets/upload     — upload text → EBCDIC FB dataset record
  POST /zos/datasets/download   — download EBCDIC dataset record → UTF-8 text
  GET  /zos/jobs                — list submitted JCL jobs
  POST /zos/jobs                — submit a JCL job
  GET  /zos/jobs/{job_id}       — get job status
  DELETE /zos/jobs/{job_id}     — cancel a job
  GET  /zos/mqbridge            — queue depth summary
  POST /zos/mqbridge/put        — put a message onto a queue
  GET  /zos/mqbridge/get        — destructive get from a queue
"""

from __future__ import annotations

import base64
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.identity.security import TokenPayload
from zos_bridge.codec import CodePage, EbcdicCodec
from zos_bridge.dataset import DatasetParser, RecordFormat
from zos_bridge.jcl import (
    DDStatement, JCLBuilder, JCLJob, JCLStep, JobCompletionCode, JobStatus,
)
from zos_bridge.lpar import LPARConfig, LPARConnection, LPARMetrics, LPARStatus, ZOSVersion
from zos_bridge.mq import MQBridgeAdapter, MQMessage, MQMessageType, MQPersistence
from zos_bridge.racf import RACFAccessList, RACFPermission, RACFProfile

router = APIRouter(prefix="/zos", tags=["z/OS"])

Analyst = Depends(require_roles("analyst", "quant", "trader"))
Admin   = Depends(require_roles("admin", "owner"))

# ── Singleton sandbox state ───────────────────────────────────────────────────
# In production these are real connections; here they are in-process stubs.

_LPAR_CONFIGS: list[LPARConfig] = [
    LPARConfig(
        lpar_name="SYSA",
        sysplex_name="FINPLEX",
        system_nickname="Production LPAR A",
        zosmf_host="zosmf-a.example.com",
        zos_version=ZOSVersion.ZOS_2_5,
        cpu_model="3931",
        max_memory_gb=512,
        mq_queue_manager="QM_PROD",
    ),
    LPARConfig(
        lpar_name="SYSB",
        sysplex_name="FINPLEX",
        system_nickname="DR / Test LPAR B",
        zosmf_host="zosmf-b.example.com",
        zos_version=ZOSVersion.ZOS_3_1,
        cpu_model="3931",
        max_memory_gb=256,
        mq_queue_manager="QM_TEST",
    ),
]

_lpar_connections: dict[str, LPARConnection] = {
    cfg.lpar_name: LPARConnection(cfg) for cfg in _LPAR_CONFIGS
}
# Auto-connect both in dev mode
for _conn in _lpar_connections.values():
    _conn.connect()

_mq_adapter = MQBridgeAdapter(queue_manager="QM_FINTEK")
_mq_adapter.connect()
for _qname in ["QFINTEK.ORDERS.LOCAL", "QFINTEK.TRADES.LOCAL", "QFINTEK.AUDIT.LOCAL", "QFINTEK.RISK.LOCAL"]:
    _mq_adapter.ensure_queue(_qname)

_jobs: dict[str, JobStatus] = {}

_DATASET_CATALOGUE: list[dict[str, Any]] = [
    {"dsn": "QFINTEK.PAYROLL.MASTER",  "recfm": "FB", "lrecl": 80,  "blksize": 800,  "size_tracks": 120},
    {"dsn": "QFINTEK.TRADES.HISTORY",  "recfm": "VB", "lrecl": 255, "blksize": 2550, "size_tracks": 4400},
    {"dsn": "QFINTEK.RISK.COBOL.OBJ",  "recfm": "FB", "lrecl": 80,  "blksize": 3200, "size_tracks": 60},
    {"dsn": "QFINTEK.REPORTS.MONTHLY", "recfm": "FB", "lrecl": 133, "blksize": 1330, "size_tracks": 220},
    {"dsn": "QFINTEK.JCL.LIB",         "recfm": "FB", "lrecl": 80,  "blksize": 3200, "size_tracks": 15},
    {"dsn": "QFINTEK.LOADLIB",         "recfm": "U",  "lrecl": 0,   "blksize": 6144, "size_tracks": 500},
]

# ── Request / Response models ─────────────────────────────────────────────────

class LPAROut(BaseModel):
    lpar_name: str
    sysplex_name: str
    system_nickname: str
    zos_version: str
    cpu_model: str
    max_memory_gb: int
    mq_queue_manager: str
    status: str


class LPARMetricsOut(BaseModel):
    lpar_name: str
    status: str
    cpu_utilization_pct: float
    memory_used_gb: float
    memory_total_gb: float
    memory_used_pct: float
    ziip_utilization_pct: float
    active_jobs: int
    active_initiators: int
    mips: float
    timestamp: str


class ZOSHealthResponse(BaseModel):
    sysplex: str
    lpars: list[LPARMetricsOut]
    total_lpars: int
    online_lpars: int
    mq_queues: dict[str, int]


class TranscodeRequest(BaseModel):
    text: str = Field(..., description="UTF-8 text to encode to EBCDIC")
    code_page: str = Field("cp037", description="EBCDIC code page, e.g. cp037, cp1047, cp1140")
    record_length: int = Field(80, ge=1, le=32756, description="Fixed record length (used when mode=fixed)")
    mode: str = Field("fixed", description="fixed | raw — fixed pads/truncates to record_length")
    include_hex_dump: bool = False


class TranscodeResponse(BaseModel):
    code_page: str
    mode: str
    record_length: int
    ebcdic_b64: str             # base64-encoded EBCDIC bytes
    byte_count: int
    hex_dump: str | None = None


class TranscodeDecodeRequest(BaseModel):
    ebcdic_b64: str = Field(..., description="Base64-encoded EBCDIC bytes")
    code_page: str = Field("cp037")
    record_length: int = Field(80, ge=1, le=32756)
    mode: str = Field("fixed", description="fixed | raw")
    strip_trailing_spaces: bool = True


class TranscodeDecodeResponse(BaseModel):
    code_page: str
    lines: list[str]
    record_count: int


class DatasetOut(BaseModel):
    dsn: str
    recfm: str
    lrecl: int
    blksize: int
    size_tracks: int


class DatasetListResponse(BaseModel):
    datasets: list[DatasetOut]
    total: int


class DatasetUploadRequest(BaseModel):
    dsn: str = Field(..., description="Target dataset name, e.g. QFINTEK.PAYROLL.MASTER")
    lines: list[str] = Field(..., min_length=1, description="UTF-8 text lines to store as EBCDIC records")
    recfm: str = Field("FB")
    lrecl: int = Field(80, ge=1, le=32756)
    code_page: str = Field("cp037")


class DatasetUploadResponse(BaseModel):
    dsn: str
    records_written: int
    byte_count: int
    recfm: str
    lrecl: int
    ebcdic_b64: str


class DatasetDownloadRequest(BaseModel):
    dsn: str
    code_page: str = Field("cp037")
    max_records: int = Field(100, ge=1, le=10000)


class DatasetDownloadResponse(BaseModel):
    dsn: str
    records: list[str]
    record_count: int
    code_page: str


class JobSubmitRequest(BaseModel):
    jcl: str | None = Field(None, description="Raw JCL text to submit")
    job_name: str = Field("QFJOB", max_length=8)
    lpar: str = Field("SYSA", description="Target LPAR name")
    notify_userid: str | None = None
    # Convenience builder fields (used when jcl is None)
    program: str | None = Field(None, description="PGM= for a single-step job")
    parm: str | None = None
    input_dsn: str | None = None


class JobOut(BaseModel):
    job_id: str
    job_name: str
    lpar: str
    owner: str
    status: str
    return_code: int | None
    abend_code: str | None
    completion: str | None
    submitted_at: str
    started_at: str | None
    ended_at: str | None


class JobListResponse(BaseModel):
    jobs: list[JobOut]
    total: int


class MQPutRequest(BaseModel):
    queue_name: str = Field("QFINTEK.ORDERS.LOCAL")
    payload: str = Field(..., description="UTF-8 text payload")
    msg_type: str = Field("DATAGRAM", description="DATAGRAM | REQUEST | REPLY")
    reply_to_q: str = ""
    user_identifier: str = ""
    persist: bool = False


class MQPutResponse(BaseModel):
    queue_name: str
    msg_id: str
    queue_depth: int


class MQGetResponse(BaseModel):
    queue_name: str
    msg_id: str | None
    payload: str | None
    msg_type: str | None
    put_time: str | None
    queue_depth: int


class MQBridgeStatusResponse(BaseModel):
    queue_manager: str
    connected: bool
    queues: dict[str, int]


class RACFCheckRequest(BaseModel):
    userid: str
    groups: list[str] = []
    attributes: list[str] = []
    resource_name: str
    resource_class: str = "DATASET"


class RACFCheckResponse(BaseModel):
    userid: str
    resource_name: str
    effective_permission: str
    permitted: bool


# ── helper ────────────────────────────────────────────────────────────────────

def _lpar_conn(lpar_name: str) -> LPARConnection:
    conn = _lpar_connections.get(lpar_name.upper())
    if conn is None:
        raise HTTPException(status_code=404, detail=f"LPAR '{lpar_name}' not configured")
    return conn


def _job_to_out(j: JobStatus, lpar: str) -> JobOut:
    return JobOut(
        job_id=j.job_id,
        job_name=j.job_name,
        lpar=lpar,
        owner=j.owner,
        status=j.status,
        return_code=j.return_code,
        abend_code=j.abend_code,
        completion=j.completion.value if j.completion else None,
        submitted_at=j.submitted_at or "",
        started_at=j.started_at,
        ended_at=j.ended_at,
    )


def _simulate_job_completion(job: JobStatus) -> None:
    """Advance a freshly-submitted job to OUTPUT with a simulated RC."""
    job.status = "OUTPUT"
    job.started_at = datetime.now(timezone.utc).isoformat()
    job.ended_at = datetime.now(timezone.utc).isoformat()
    if random.random() < 0.92:
        job.return_code = random.choice([0, 0, 0, 4])
        job.completion = JobCompletionCode.CC
    else:
        job.abend_code = random.choice(["S0C7", "S322", "U4093", "S806"])
        job.completion = JobCompletionCode.ABEND


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=ZOSHealthResponse)
def zos_health(_user: TokenPayload = Analyst) -> ZOSHealthResponse:
    """Return health metrics for all configured LPARs and MQ queues."""
    lpar_metrics: list[LPARMetricsOut] = []
    online = 0
    for name, conn in _lpar_connections.items():
        m = conn.get_metrics()
        lpar_metrics.append(LPARMetricsOut(
            lpar_name=name,
            status=conn.status.value,
            cpu_utilization_pct=m.cpu_utilization_pct,
            memory_used_gb=m.memory_used_gb,
            memory_total_gb=m.memory_total_gb,
            memory_used_pct=m.memory_used_pct,
            ziip_utilization_pct=m.ziip_utilization_pct,
            active_jobs=m.active_jobs,
            active_initiators=m.active_initiators,
            mips=m.mips,
            timestamp=m.timestamp,
        ))
        if conn.status == LPARStatus.ONLINE:
            online += 1

    return ZOSHealthResponse(
        sysplex=_LPAR_CONFIGS[0].sysplex_name if _LPAR_CONFIGS else "UNKNOWN",
        lpars=lpar_metrics,
        total_lpars=len(_lpar_connections),
        online_lpars=online,
        mq_queues=_mq_adapter.queue_depths(),
    )


@router.get("/lpars", response_model=list[LPAROut])
def list_lpars(_user: TokenPayload = Analyst) -> list[LPAROut]:
    return [
        LPAROut(
            lpar_name=cfg.lpar_name,
            sysplex_name=cfg.sysplex_name,
            system_nickname=cfg.system_nickname,
            zos_version=cfg.zos_version.value,
            cpu_model=cfg.cpu_model,
            max_memory_gb=cfg.max_memory_gb,
            mq_queue_manager=cfg.mq_queue_manager,
            status=_lpar_connections[cfg.lpar_name].status.value,
        )
        for cfg in _LPAR_CONFIGS
    ]


# ── transcoding ───────────────────────────────────────────────────────────────

@router.post("/transcode", response_model=TranscodeResponse)
def transcode_to_ebcdic(
    body: TranscodeRequest,
    _user: TokenPayload = Analyst,
) -> TranscodeResponse:
    """Encode UTF-8 text to EBCDIC bytes (returns base64)."""
    try:
        cp = CodePage(body.code_page)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown code page: {body.code_page!r}")
    codec = EbcdicCodec(cp)
    if body.mode == "fixed":
        raw = codec.encode_lines(body.text.splitlines() or [""], body.record_length)
    else:
        raw = codec.encode(body.text)
    return TranscodeResponse(
        code_page=body.code_page,
        mode=body.mode,
        record_length=body.record_length,
        ebcdic_b64=base64.b64encode(raw).decode(),
        byte_count=len(raw),
        hex_dump=codec.hex_dump(raw[:256]) if body.include_hex_dump else None,
    )


@router.post("/transcode/decode", response_model=TranscodeDecodeResponse)
def transcode_from_ebcdic(
    body: TranscodeDecodeRequest,
    _user: TokenPayload = Analyst,
) -> TranscodeDecodeResponse:
    """Decode EBCDIC bytes (base64) to UTF-8 text lines."""
    try:
        raw = base64.b64decode(body.ebcdic_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 in ebcdic_b64")
    try:
        cp = CodePage(body.code_page)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown code page: {body.code_page!r}")
    codec = EbcdicCodec(cp)
    if body.mode == "fixed":
        lines = codec.decode_lines(raw, body.record_length, strip=body.strip_trailing_spaces)
    else:
        lines = [codec.decode(raw, errors="replace")]
    return TranscodeDecodeResponse(code_page=body.code_page, lines=lines, record_count=len(lines))


# ── datasets ──────────────────────────────────────────────────────────────────

@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets(
    hlq: str = Query("QFINTEK", description="High-level qualifier filter"),
    _user: TokenPayload = Analyst,
) -> DatasetListResponse:
    """List datasets in the simulated MVS catalogue."""
    filtered = [d for d in _DATASET_CATALOGUE if d["dsn"].startswith(hlq.upper())]
    return DatasetListResponse(
        datasets=[DatasetOut(**d) for d in filtered],
        total=len(filtered),
    )


@router.post("/datasets/upload", response_model=DatasetUploadResponse)
def upload_dataset(
    body: DatasetUploadRequest,
    _user: TokenPayload = Analyst,
) -> DatasetUploadResponse:
    """Encode UTF-8 lines to EBCDIC and write them as a z/OS dataset record block."""
    try:
        cp = CodePage(body.code_page)
        recfm = RecordFormat(body.recfm.upper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    parser = DatasetParser(recfm=recfm, lrecl=body.lrecl, code_page=cp)
    raw = parser.build(body.lines)
    return DatasetUploadResponse(
        dsn=body.dsn.upper(),
        records_written=len(body.lines),
        byte_count=len(raw),
        recfm=body.recfm.upper(),
        lrecl=body.lrecl,
        ebcdic_b64=base64.b64encode(raw).decode(),
    )


@router.post("/datasets/download", response_model=DatasetDownloadResponse)
def download_dataset(
    body: DatasetDownloadRequest,
    _user: TokenPayload = Analyst,
) -> DatasetDownloadResponse:
    """Simulate downloading an EBCDIC dataset and decoding it to UTF-8."""
    entry = next((d for d in _DATASET_CATALOGUE if d["dsn"] == body.dsn.upper()), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{body.dsn.upper()}' not in catalogue")
    # Generate synthetic EBCDIC content for the stub
    try:
        cp = CodePage(body.code_page)
        recfm = RecordFormat(entry["recfm"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    lrecl: int = entry["lrecl"] or 80
    codec = EbcdicCodec(cp)
    sample_lines = [
        f"{body.dsn.upper():<44}  RECORD {i:06d}  GENERATED BY QUANTUMFINTEK ZOSMF STUB"
        for i in range(min(body.max_records, 20))
    ]
    parser = DatasetParser(recfm=recfm, lrecl=lrecl, code_page=cp)
    raw = parser.build(sample_lines)
    records = parser.parse(raw)
    return DatasetDownloadResponse(
        dsn=body.dsn.upper(),
        records=[r.text for r in records],
        record_count=len(records),
        code_page=body.code_page,
    )


# ── jobs ──────────────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    lpar: str = Query("SYSA"),
    job_status: str | None = Query(None, alias="status"),
    _user: TokenPayload = Analyst,
) -> JobListResponse:
    """List submitted JCL jobs (filtered optionally by LPAR / status)."""
    jobs = [
        _job_to_out(j, lpar)
        for j in _jobs.values()
        if (job_status is None or j.status == job_status.upper())
    ]
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def submit_job(
    body: JobSubmitRequest,
    user: TokenPayload = Analyst,
) -> JobOut:
    """Submit a JCL job to z/OS (stub: simulates JES2 accept + execution)."""
    _lpar_conn(body.lpar)  # validates LPAR exists

    # Build JCL if not provided verbatim
    if body.jcl is None:
        prog = body.program or "IEFBR14"
        builder = JCLBuilder(job_name=body.job_name, account="QFINTEK")
        if body.notify_userid:
            builder.notify(body.notify_userid)
        sb = builder.step("STEP1", program=prog, parm=body.parm)
        if body.input_dsn:
            sb.dd(dd_name="SYSIN", dsn=body.input_dsn, disp="SHR")
        sb.dd(dd_name="SYSPRINT", sysout="*")
        sb.dd(dd_name="SYSOUT", sysout="*")
    # (raw JCL accepted but not parsed in stub)

    job_id = f"JOB{random.randint(10000, 99999)}"
    now = datetime.now(timezone.utc).isoformat()
    job = JobStatus(
        job_id=job_id,
        job_name=body.job_name.upper()[:8],
        owner=user.sub[:8] if user.sub else "UNKNOWN",
        status="INPUT",
        submitted_at=now,
    )
    _simulate_job_completion(job)
    _jobs[job_id] = job
    return _job_to_out(job, body.lpar)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    lpar: str = Query("SYSA"),
    _user: TokenPayload = Analyst,
) -> JobOut:
    job = _jobs.get(job_id.upper())
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return _job_to_out(job, lpar)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_job(
    job_id: str,
    _user: TokenPayload = Analyst,
) -> None:
    job = _jobs.get(job_id.upper())
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job.is_complete:
        raise HTTPException(status_code=409, detail=f"Job '{job_id}' is already complete ({job.status})")
    job.status = "CANCELLED"
    job.completion = JobCompletionCode.CANCEL
    job.ended_at = datetime.now(timezone.utc).isoformat()


# ── MQ bridge ─────────────────────────────────────────────────────────────────

@router.get("/mqbridge", response_model=MQBridgeStatusResponse)
def mq_status(_user: TokenPayload = Analyst) -> MQBridgeStatusResponse:
    """Return MQ bridge connection state and queue depths."""
    return MQBridgeStatusResponse(
        queue_manager=_mq_adapter.queue_manager,
        connected=_mq_adapter.is_connected,
        queues=_mq_adapter.queue_depths(),
    )


@router.post("/mqbridge/put", response_model=MQPutResponse)
def mq_put(
    body: MQPutRequest,
    user: TokenPayload = Analyst,
) -> MQPutResponse:
    """Put a message onto a z/OS MQ queue."""
    try:
        msg_type = MQMessageType(body.msg_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid msg_type: {body.msg_type!r}")
    msg = MQMessage.from_text(
        body.payload,
        msg_type=msg_type,
        reply_to_q=body.reply_to_q,
        user_identifier=(user.sub or "")[:12],
        persistence=MQPersistence.PERSISTENT if body.persist else MQPersistence.NOT_PERSISTENT,
    )
    try:
        msg_id = _mq_adapter.put(body.queue_name, msg)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return MQPutResponse(
        queue_name=body.queue_name,
        msg_id=msg_id,
        queue_depth=_mq_adapter.queue_depths().get(body.queue_name, 0),
    )


@router.get("/mqbridge/get", response_model=MQGetResponse)
def mq_get(
    queue_name: str = Query("QFINTEK.ORDERS.LOCAL"),
    _user: TokenPayload = Analyst,
) -> MQGetResponse:
    """Destructively get the next message from a z/OS MQ queue."""
    msg = _mq_adapter.get(queue_name)
    depth = _mq_adapter.queue_depths().get(queue_name, 0)
    if msg is None:
        return MQGetResponse(
            queue_name=queue_name, msg_id=None, payload=None,
            msg_type=None, put_time=None, queue_depth=depth,
        )
    return MQGetResponse(
        queue_name=queue_name,
        msg_id=msg.msg_id,
        payload=msg.payload_text,
        msg_type=msg.msg_type.value,
        put_time=msg.put_time,
        queue_depth=depth,
    )


# ── RACF ──────────────────────────────────────────────────────────────────────

@router.post("/racf/check", response_model=RACFCheckResponse)
def racf_check(
    body: RACFCheckRequest,
    _user: TokenPayload = Analyst,
) -> RACFCheckResponse:
    """Evaluate effective RACF permission for a user on a resource (simulation)."""
    profile = RACFProfile(
        userid=body.userid,
        groups=body.groups,
        attributes=body.attributes,
    )
    acl = RACFAccessList(
        resource_name=body.resource_name,
        resource_class=body.resource_class,
        uacc=RACFPermission.READ,
    )
    # Simulate: owners get ALTER, FINGRP gets UPDATE
    acl.permit("SYS1",   RACFPermission.ALTER,  "GROUP")
    acl.permit("FINGRP", RACFPermission.UPDATE, "GROUP")
    perm = acl.check(profile)
    return RACFCheckResponse(
        userid=profile.userid,
        resource_name=body.resource_name,
        effective_permission=perm.name,
        permitted=perm >= RACFPermission.READ,
    )
