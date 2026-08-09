"""LPAR (Logical Partition) connection configuration and health model.

Models an IBM Z-series LPAR for connection purposes:
  - LPARConfig       — static connection parameters
  - LPARConnection   — runtime connection state + z/OSMF REST API helpers
  - Sysplex topology — multi-LPAR group awareness

In production, LPARConnection.request() calls the real z/OSMF REST API
(port 443 by default).  Here it is simulated for sandbox/dev use.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class LPARStatus(str, Enum):
    ONLINE    = "ONLINE"
    OFFLINE   = "OFFLINE"
    DEGRADED  = "DEGRADED"
    UNKNOWN   = "UNKNOWN"


class ZOSVersion(str, Enum):
    ZOS_2_4 = "2.4"
    ZOS_2_5 = "2.5"
    ZOS_3_1 = "3.1"


@dataclass
class LPARConfig:
    """Static configuration for an IBM Z LPAR / z/OSMF endpoint."""

    # Identity
    lpar_name: str                          # e.g. "SYSA"
    sysplex_name: str = "PLEX1"             # sysplex the LPAR belongs to
    system_nickname: str = ""               # friendly name

    # z/OSMF connectivity
    zosmf_host: str = "zosmf.example.com"
    zosmf_port: int = 443
    zosmf_base_path: str = "/zosmf/restjobs/jobs"
    tls_verify: bool = True                 # set False only in dev/test

    # Authentication (in production: use passtickets or client certs)
    username: str = ""
    password: str = ""                      # store in vault, never in code

    # Hardware / capacity hints
    zos_version: ZOSVersion = ZOSVersion.ZOS_2_5
    cpu_model: str = "3931"                 # IBM z16 = 3931
    lpar_weight: int = 100                  # relative processing weight
    max_memory_gb: int = 256

    # MQ Queue Manager
    mq_queue_manager: str = "QM_PROD"
    mq_channel: str = "SYSTEM.DEF.SVRCONN"
    mq_host: str = ""
    mq_port: int = 1414

    def __post_init__(self) -> None:
        self.lpar_name = self.lpar_name.upper()[:8]
        self.sysplex_name = self.sysplex_name.upper()[:8]

    @property
    def zosmf_base_url(self) -> str:
        proto = "https" if self.tls_verify else "http"
        return f"{proto}://{self.zosmf_host}:{self.zosmf_port}"


@dataclass
class LPARMetrics:
    """Point-in-time performance metrics for an LPAR."""
    cpu_utilization_pct: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    ziip_utilization_pct: float = 0.0     # zIIP (specialty engine) utilization
    active_jobs: int = 0
    active_initiators: int = 0
    mips: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def memory_used_pct(self) -> float:
        if self.memory_total_gb <= 0:
            return 0.0
        return round(self.memory_used_gb / self.memory_total_gb * 100, 1)


class LPARConnection:
    """Runtime connection state for an IBM Z LPAR.

    In production, call connect() to establish an authenticated z/OSMF session.
    The stub simulates connectivity and returns realistic-looking metrics.
    """

    def __init__(self, config: LPARConfig) -> None:
        self.config = config
        self._status: LPARStatus = LPARStatus.OFFLINE
        self._session_id: Optional[str] = None

    def connect(self) -> bool:
        """Establish connection (stub: always succeeds)."""
        self._session_id = uuid.uuid4().hex
        self._status = LPARStatus.ONLINE
        return True

    def disconnect(self) -> None:
        self._session_id = None
        self._status = LPARStatus.OFFLINE

    @property
    def is_connected(self) -> bool:
        return self._status == LPARStatus.ONLINE

    @property
    def status(self) -> LPARStatus:
        return self._status

    def get_metrics(self) -> LPARMetrics:
        """Return simulated LPAR metrics (stub)."""
        total = float(self.config.max_memory_gb)
        used  = round(total * random.uniform(0.45, 0.85), 1)
        return LPARMetrics(
            cpu_utilization_pct=round(random.uniform(5, 75), 1),
            memory_used_gb=used,
            memory_total_gb=total,
            ziip_utilization_pct=round(random.uniform(0, 60), 1),
            active_jobs=random.randint(8, 256),
            active_initiators=random.randint(4, 32),
            mips=round(random.uniform(500, 4000), 1),
        )

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Stub HTTP request to z/OSMF REST API."""
        if not self.is_connected:
            raise RuntimeError("Not connected to LPAR")
        return {"status": "stub", "lpar": self.config.lpar_name, "path": path}
