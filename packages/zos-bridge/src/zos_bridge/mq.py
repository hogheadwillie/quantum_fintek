"""IBM MQ (MQI) stub adapter for z/OS message queuing.

Models the core MQI concepts:
  - MQMessage   — message descriptor (MQMD) + payload
  - MQQueue     — in-memory FIFO queue (production: backed by real MQ broker)
  - MQBridgeAdapter — put/get/browse/commit operations

This is a pure-Python simulation. In production, replace with pymqi or
ibm-mq python bindings pointed at a real Queue Manager.

Ref: IBM MQ 9.3 Application Programming Reference
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Deque, Optional


class MQPersistence(str, Enum):
    NOT_PERSISTENT = "NOT_PERSISTENT"   # MQPER_NOT_PERSISTENT
    PERSISTENT     = "PERSISTENT"       # MQPER_PERSISTENT


class MQMessageType(str, Enum):
    DATAGRAM = "DATAGRAM"    # MQMT_DATAGRAM — fire and forget
    REQUEST  = "REQUEST"     # MQMT_REQUEST   — expect reply
    REPLY    = "REPLY"       # MQMT_REPLY
    REPORT   = "REPORT"      # MQMT_REPORT


@dataclass
class MQMessage:
    """Represents an IBM MQ message (MQMD + payload).

    Field names mirror the IBM MQMD structure where applicable.
    """

    # MQMD fields
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex.upper())
    correl_id: str = ""                                     # MQMD.CorrelId
    msg_type: MQMessageType = MQMessageType.DATAGRAM
    persistence: MQPersistence = MQPersistence.NOT_PERSISTENT
    format: str = "MQSTR   "                                # MQMD.Format (8 chars, space-padded)
    reply_to_q: str = ""                                    # MQMD.ReplyToQ
    reply_to_qmgr: str = ""                                 # MQMD.ReplyToQMgr
    expiry: int = -1                                        # -1 = MQEI_UNLIMITED (tenths of second)
    put_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    application_name: str = "QFINTEK"
    user_identifier: str = ""                               # MQMD.UserIdentifier (max 12 chars)

    # Payload
    payload: bytes = b""
    encoding: str = "utf-8"                                 # payload encoding hint

    @property
    def payload_text(self) -> str:
        return self.payload.decode(self.encoding, errors="replace")

    @classmethod
    def from_text(
        cls,
        text: str,
        encoding: str = "utf-8",
        **kwargs,
    ) -> "MQMessage":
        return cls(payload=text.encode(encoding), encoding=encoding, **kwargs)

    @classmethod
    def from_ebcdic(
        cls,
        data: bytes,
        code_page: str = "cp037",
        **kwargs,
    ) -> "MQMessage":
        """Create a message from raw EBCDIC bytes (e.g. from a z/OS COBOL program)."""
        text = data.decode(code_page, errors="replace")
        return cls(
            payload=data,
            encoding=code_page,
            format="MQSTR   ",
            **kwargs,
        )

    def to_ebcdic(self, code_page: str = "cp037") -> bytes:
        """Re-encode the decoded payload to EBCDIC bytes."""
        return self.payload_text.encode(code_page, errors="replace")


@dataclass
class MQQueue:
    """In-memory MQ queue (production: replace with pymqi QueueManager connection)."""

    name: str                  # Queue name, e.g. "QFINTEK.ORDERS.LOCAL"
    max_depth: int = 999_999   # MAXDEPTH attribute
    _messages: Deque[MQMessage] = field(default_factory=deque, repr=False)
    _committed: list[MQMessage] = field(default_factory=list, repr=False)
    _uncommitted: list[MQMessage] = field(default_factory=list, repr=False)

    @property
    def depth(self) -> int:
        return len(self._messages)

    @property
    def is_full(self) -> bool:
        return self.depth >= self.max_depth

    def put(self, msg: MQMessage, sync_point: bool = False) -> str:
        """Put a message. Returns msg_id. Raises if queue full."""
        if self.is_full:
            raise RuntimeError(f"MQRC_Q_FULL: queue {self.name!r} is at max depth {self.max_depth}")
        if sync_point:
            self._uncommitted.append(msg)
        else:
            self._messages.append(msg)
        return msg.msg_id

    def get(self, wait_ms: int = 0) -> Optional[MQMessage]:
        """Destructive get from head of queue. Returns None if empty."""
        if self._messages:
            return self._messages.popleft()
        return None

    def browse(self) -> Optional[MQMessage]:
        """Non-destructive peek at the head message."""
        return self._messages[0] if self._messages else None

    def commit(self) -> int:
        """Commit all messages in the current sync-point unit of work."""
        n = len(self._uncommitted)
        for msg in self._uncommitted:
            self._messages.append(msg)
        self._uncommitted.clear()
        return n

    def backout(self) -> int:
        """Roll back all uncommitted puts."""
        n = len(self._uncommitted)
        self._uncommitted.clear()
        return n


class MQBridgeAdapter:
    """High-level MQ bridge: manages a set of named queues and routes messages.

    In production, swap _queues with a real pymqi.QueueManager session.
    """

    def __init__(self, queue_manager: str = "QM_QFINTEK") -> None:
        self.queue_manager = queue_manager
        self._queues: dict[str, MQQueue] = {}
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def ensure_queue(self, name: str, max_depth: int = 999_999) -> MQQueue:
        if name not in self._queues:
            self._queues[name] = MQQueue(name=name, max_depth=max_depth)
        return self._queues[name]

    def put(self, queue_name: str, msg: MQMessage, sync_point: bool = False) -> str:
        q = self.ensure_queue(queue_name)
        return q.put(msg, sync_point=sync_point)

    def get(self, queue_name: str, wait_ms: int = 0) -> Optional[MQMessage]:
        q = self.ensure_queue(queue_name)
        return q.get(wait_ms=wait_ms)

    def queue_depths(self) -> dict[str, int]:
        return {name: q.depth for name, q in self._queues.items()}

    @property
    def is_connected(self) -> bool:
        return self._connected
