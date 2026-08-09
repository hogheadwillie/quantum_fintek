"""EBCDIC ↔ UTF-8 transcoding for IBM z/OS code pages.

Supported code pages:
  IBM-037   — US English (most common EBCDIC)
  IBM-1047  — Open Systems (Unix-on-zOS, POSIX)
  IBM-1140  — US English + Euro sign (modern batch/COBOL)
  IBM-500   — International EBCDIC

Python's ``codecs`` module ships built-in support for these as
``cp037``, ``cp1047``, ``cp1140``, ``cp500`` respectively.
"""

from __future__ import annotations

import codecs
from enum import Enum


class CodePage(str, Enum):
    IBM_037  = "cp037"    # US EBCDIC — classic batch / COBOL
    IBM_1047 = "cp1047"   # Open Systems / USS
    IBM_1140 = "cp1140"   # US EBCDIC + Euro €
    IBM_500  = "cp500"    # International EBCDIC
    IBM_273  = "cp273"    # German EBCDIC
    IBM_280  = "cp280"    # Italian EBCDIC
    IBM_284  = "cp284"    # Spanish / Latin-American EBCDIC
    IBM_285  = "cp285"    # UK English EBCDIC
    IBM_297  = "cp297"    # French EBCDIC
    IBM_1141 = "cp1141"   # German + Euro
    IBM_1148 = "cp1148"   # International + Euro


class EbcdicCodec:
    """Encode/decode between EBCDIC byte strings and Python unicode strings."""

    def __init__(self, code_page: CodePage = CodePage.IBM_037) -> None:
        self.code_page = code_page
        # Validate the codec is available
        codecs.lookup(code_page.value)

    # ── encode (UTF-8 str → EBCDIC bytes) ────────────────────────────────────

    def encode(self, text: str, errors: str = "replace") -> bytes:
        """Encode a UTF-8 string to EBCDIC bytes."""
        return text.encode(self.code_page.value, errors=errors)

    def encode_record(
        self,
        text: str,
        record_length: int,
        pad_char: str = " ",
        errors: str = "replace",
    ) -> bytes:
        """Encode *text* to a fixed-length EBCDIC record, padding or truncating."""
        padded = text.ljust(record_length, pad_char)[:record_length]
        return padded.encode(self.code_page.value, errors=errors)

    # ── decode (EBCDIC bytes → UTF-8 str) ────────────────────────────────────

    def decode(self, data: bytes, errors: str = "replace") -> str:
        """Decode EBCDIC bytes to a UTF-8 string."""
        return data.decode(self.code_page.value, errors=errors)

    def decode_record(self, data: bytes, strip: bool = True, errors: str = "replace") -> str:
        """Decode a fixed-length EBCDIC record, optionally stripping trailing spaces."""
        text = data.decode(self.code_page.value, errors=errors)
        return text.rstrip(" ") if strip else text

    # ── batch helpers ─────────────────────────────────────────────────────────

    def encode_lines(self, lines: list[str], record_length: int) -> bytes:
        """Encode a list of strings into a flat fixed-block EBCDIC byte stream."""
        buf = bytearray()
        for line in lines:
            buf += self.encode_record(line, record_length)
        return bytes(buf)

    def decode_lines(self, data: bytes, record_length: int, strip: bool = True) -> list[str]:
        """Split a flat fixed-block EBCDIC byte stream into decoded lines."""
        if record_length <= 0:
            raise ValueError("record_length must be > 0")
        lines: list[str] = []
        for i in range(0, len(data), record_length):
            chunk = data[i : i + record_length]
            lines.append(self.decode_record(chunk, strip=strip))
        return lines

    # ── utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def available_code_pages() -> list[str]:
        return [cp.value for cp in CodePage]

    def hex_dump(self, data: bytes, width: int = 16) -> str:
        """Return a hex + EBCDIC-decoded dump of *data* for diagnostics."""
        lines: list[str] = []
        for i in range(0, len(data), width):
            chunk = data[i : i + width]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            try:
                chr_part = "".join(
                    c if c.isprintable() else "." for c in chunk.decode(self.code_page.value, errors="replace")
                )
            except Exception:
                chr_part = "." * len(chunk)
            lines.append(f"{i:08X}  {hex_part:<{width * 3}}  |{chr_part}|")
        return "\n".join(lines)
