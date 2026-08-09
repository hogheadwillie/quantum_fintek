"""MVS dataset record-format support.

Supports the four standard z/OS RECFM values:
  F   — Fixed, unblocked (one logical record = physical record)
  FB  — Fixed Blocked (block = N × LRECL)
  V   — Variable, unblocked (4-byte RDW prefix)
  VB  — Variable Blocked (4-byte BDW prefix, then N × (4-byte RDW + data))
  U   — Undefined (raw bytes, no structure)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from .codec import CodePage, EbcdicCodec


class RecordFormat(str, Enum):
    F  = "F"   # Fixed unblocked
    FB = "FB"  # Fixed blocked
    V  = "V"   # Variable unblocked
    VB = "VB"  # Variable blocked
    U  = "U"   # Undefined


@dataclass
class DatasetRecord:
    """A single logical record from a z/OS dataset."""

    data: bytes                       # raw EBCDIC bytes
    record_format: RecordFormat
    lrecl: int                        # logical record length (0 for V/VB/U)
    sequence: int = 0                 # 0-based record index
    codec: EbcdicCodec = field(default_factory=EbcdicCodec, repr=False)

    @property
    def text(self) -> str:
        """Decoded UTF-8 text of this record."""
        return self.codec.decode_record(self.data)

    @property
    def length(self) -> int:
        return len(self.data)


class DatasetParser:
    """Parse raw z/OS dataset byte streams into DatasetRecord objects."""

    def __init__(
        self,
        recfm: RecordFormat = RecordFormat.FB,
        lrecl: int = 80,
        blksize: int = 0,
        code_page: CodePage = CodePage.IBM_037,
    ) -> None:
        self.recfm = recfm
        self.lrecl = lrecl
        self.blksize = blksize or (lrecl * 10)
        self.codec = EbcdicCodec(code_page)

    # ── parse ─────────────────────────────────────────────────────────────────

    def parse(self, raw: bytes) -> list[DatasetRecord]:
        return list(self._iter_records(raw))

    def _iter_records(self, raw: bytes) -> Iterator[DatasetRecord]:
        seq = 0
        match self.recfm:
            case RecordFormat.F:
                yield from self._parse_fixed(raw, self.lrecl, seq)
            case RecordFormat.FB:
                yield from self._parse_fixed(raw, self.lrecl, seq)
            case RecordFormat.V:
                yield from self._parse_variable(raw, seq, blocked=False)
            case RecordFormat.VB:
                yield from self._parse_variable(raw, seq, blocked=True)
            case RecordFormat.U:
                yield DatasetRecord(
                    data=raw,
                    record_format=self.recfm,
                    lrecl=len(raw),
                    sequence=seq,
                    codec=self.codec,
                )

    def _parse_fixed(self, raw: bytes, lrecl: int, start_seq: int) -> Iterator[DatasetRecord]:
        seq = start_seq
        for i in range(0, len(raw), lrecl):
            chunk = raw[i : i + lrecl]
            if not chunk:
                break
            yield DatasetRecord(
                data=chunk,
                record_format=self.recfm,
                lrecl=lrecl,
                sequence=seq,
                codec=self.codec,
            )
            seq += 1

    def _parse_variable(self, raw: bytes, start_seq: int, blocked: bool) -> Iterator[DatasetRecord]:
        """Parse V or VB format.

        V:  Each record prefixed by a 4-byte RDW (Record Descriptor Word).
            RDW[0:2] = total length including RDW (big-endian uint16).
        VB: Stream prefixed by 4-byte BDW (Block Descriptor Word), then V records.
        """
        seq = start_seq
        offset = 0

        if blocked:
            # Skip BDW prefix
            if len(raw) < 4:
                return
            offset = 4  # skip BDW

        while offset + 4 <= len(raw):
            rdw = raw[offset : offset + 4]
            rec_len = struct.unpack(">H", rdw[0:2])[0]
            if rec_len < 4 or offset + rec_len > len(raw):
                break
            data = raw[offset + 4 : offset + rec_len]
            yield DatasetRecord(
                data=data,
                record_format=self.recfm,
                lrecl=len(data),
                sequence=seq,
                codec=self.codec,
            )
            seq += 1
            offset += rec_len

    # ── build (write) ─────────────────────────────────────────────────────────

    def build(self, records: list[str]) -> bytes:
        """Encode text records into a z/OS dataset byte stream."""
        match self.recfm:
            case RecordFormat.F | RecordFormat.FB:
                return self.codec.encode_lines(records, self.lrecl)
            case RecordFormat.V | RecordFormat.VB:
                return self._build_variable(records, blocked=(self.recfm == RecordFormat.VB))
            case RecordFormat.U:
                return b"".join(r.encode("utf-8") for r in records)

    def _build_variable(self, records: list[str], blocked: bool) -> bytes:
        body = bytearray()
        for rec in records:
            enc = self.codec.encode(rec)
            rdw_len = len(enc) + 4
            rdw = struct.pack(">HH", rdw_len, 0)
            body += rdw + enc
        if blocked:
            bdw_len = len(body) + 4
            bdw = struct.pack(">HH", bdw_len, 0)
            return bytes(bdw) + bytes(body)
        return bytes(body)
