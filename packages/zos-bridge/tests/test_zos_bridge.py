"""Tests for zos-bridge package."""

from __future__ import annotations

import base64
import struct

import pytest

from zos_bridge.codec import CodePage, EbcdicCodec
from zos_bridge.dataset import DatasetParser, RecordFormat
from zos_bridge.jcl import DDStatement, JCLBuilder, JobCompletionCode, JobStatus
from zos_bridge.lpar import LPARConfig, LPARConnection, ZOSVersion
from zos_bridge.mq import MQBridgeAdapter, MQMessage, MQMessageType
from zos_bridge.racf import RACFAccessList, RACFPermission, RACFProfile


# ── EbcdicCodec ───────────────────────────────────────────────────────────────

class TestEbcdicCodec:
    def test_roundtrip_ibm037(self):
        codec = EbcdicCodec(CodePage.IBM_037)
        text = "HELLO WORLD"
        assert codec.decode(codec.encode(text)) == text

    def test_roundtrip_ibm1047(self):
        import codecs as _codecs
        try:
            _codecs.lookup("cp1047")
        except LookupError:
            pytest.skip("cp1047 not available on this platform (Linux-only)")
        codec = EbcdicCodec(CodePage.IBM_1047)
        text = "QuantumFintek v0.8"
        assert codec.decode(codec.encode(text)) == text

    def test_encode_record_pads_to_lrecl(self):
        codec = EbcdicCodec()
        rec = codec.encode_record("HELLO", 80)
        assert len(rec) == 80

    def test_encode_record_truncates(self):
        codec = EbcdicCodec()
        rec = codec.encode_record("A" * 100, 80)
        assert len(rec) == 80

    def test_decode_record_strips_spaces(self):
        codec = EbcdicCodec()
        rec = codec.encode_record("HELLO", 80)
        assert codec.decode_record(rec, strip=True) == "HELLO"

    def test_encode_lines_roundtrip(self):
        codec = EbcdicCodec()
        lines = ["LINE ONE", "LINE TWO", "LINE THREE"]
        raw = codec.encode_lines(lines, 80)
        assert len(raw) == 3 * 80
        decoded = codec.decode_lines(raw, 80)
        assert decoded[0] == "LINE ONE"
        assert decoded[2] == "LINE THREE"

    def test_hex_dump_returns_string(self):
        codec = EbcdicCodec()
        raw = codec.encode("HELLO")
        dump = codec.hex_dump(raw)
        assert "HELLO" in dump or len(dump) > 0

    def test_available_code_pages(self):
        pages = EbcdicCodec.available_code_pages()
        assert "cp037" in pages
        assert "cp1047" in pages


# ── DatasetParser (FB) ────────────────────────────────────────────────────────

class TestDatasetParserFB:
    def test_build_and_parse_fb(self):
        parser = DatasetParser(recfm=RecordFormat.FB, lrecl=80)
        lines = ["RECORD ALPHA", "RECORD BETA", "RECORD GAMMA"]
        raw = parser.build(lines)
        assert len(raw) == 3 * 80
        records = parser.parse(raw)
        assert len(records) == 3
        assert records[0].text == "RECORD ALPHA"
        assert records[2].text == "RECORD GAMMA"

    def test_record_length_correct(self):
        parser = DatasetParser(recfm=RecordFormat.FB, lrecl=133)
        raw = parser.build(["REPORT LINE"])
        assert len(raw) == 133
        recs = parser.parse(raw)
        assert recs[0].lrecl == 133

    def test_empty_input(self):
        parser = DatasetParser(recfm=RecordFormat.FB, lrecl=80)
        raw = parser.build([])
        assert raw == b""


# ── DatasetParser (VB) ────────────────────────────────────────────────────────

class TestDatasetParserVB:
    def test_build_and_parse_vb(self):
        parser = DatasetParser(recfm=RecordFormat.VB, lrecl=255)
        lines = ["SHORT", "A MUCH LONGER VARIABLE RECORD HERE"]
        raw = parser.build(lines)
        records = parser.parse(raw)
        assert len(records) == 2
        assert records[0].text == "SHORT"
        assert "LONGER" in records[1].text

    def test_variable_record_lengths_differ(self):
        parser = DatasetParser(recfm=RecordFormat.VB, lrecl=255)
        raw = parser.build(["A", "BB", "CCC"])
        records = parser.parse(raw)
        assert records[0].length < records[2].length


# ── JCLBuilder ────────────────────────────────────────────────────────────────

class TestJCLBuilder:
    def test_simple_job_render(self):
        jcl = (
            JCLBuilder("TESTJOB")
            .comment("Test job")
            .step("STEP1", program="IEFBR14")
            .dd(dd_name="SYSPRINT", sysout="*")
            .dd(dd_name="SYSOUT", sysout="*")
            .end_step()
            .render()
        )
        assert "//TESTJOB " in jcl
        assert "EXEC PGM=IEFBR14" in jcl
        assert "SYSPRINT" in jcl
        assert "SYSOUT=*" in jcl

    def test_job_name_uppercased(self):
        jcl = JCLBuilder("myjob").render()
        assert "//MYJOB   " in jcl

    def test_job_name_truncated_to_8(self):
        jcl = JCLBuilder("TOOLONGNAME").render()
        assert "//TOOLONGN" in jcl

    def test_dd_with_dsn(self):
        jcl = (
            JCLBuilder("J")
            .step("S1", program="SORT")
            .dd(dd_name="SORTIN", dsn="MY.INPUT.FILE", disp="SHR")
            .end_step()
            .render()
        )
        assert "MY.INPUT.FILE" in jcl
        assert "DISP=SHR" in jcl

    def test_job_status_succeeded(self):
        js = JobStatus(job_id="JOB12345", job_name="TESTJOB", status="OUTPUT",
                       return_code=0, completion=JobCompletionCode.CC)
        assert js.succeeded
        assert not js.failed


# ── LPAR connection ───────────────────────────────────────────────────────────

class TestLPARConnection:
    def test_connect_sets_online(self):
        cfg = LPARConfig(lpar_name="TESTA", zos_version=ZOSVersion.ZOS_2_5)
        conn = LPARConnection(cfg)
        assert not conn.is_connected
        conn.connect()
        assert conn.is_connected

    def test_metrics_ranges(self):
        cfg = LPARConfig(lpar_name="TESTB", max_memory_gb=128)
        conn = LPARConnection(cfg)
        conn.connect()
        m = conn.get_metrics()
        assert 0 <= m.cpu_utilization_pct <= 100
        assert 0 <= m.memory_used_gb <= 128
        assert m.mips > 0

    def test_request_requires_connection(self):
        cfg = LPARConfig(lpar_name="TESTC")
        conn = LPARConnection(cfg)
        with pytest.raises(RuntimeError, match="Not connected"):
            conn.request("GET", "/zosmf/info")


# ── MQ bridge ─────────────────────────────────────────────────────────────────

class TestMQBridge:
    def setup_method(self):
        self.adapter = MQBridgeAdapter("QM_TEST")
        self.adapter.connect()

    def test_put_and_get_roundtrip(self):
        msg = MQMessage.from_text("Hello from QuantumFintek")
        qname = "TEST.Q"
        self.adapter.put(qname, msg)
        got = self.adapter.get(qname)
        assert got is not None
        assert got.payload_text == "Hello from QuantumFintek"

    def test_get_empty_returns_none(self):
        result = self.adapter.get("EMPTY.Q")
        assert result is None

    def test_queue_depth_increments(self):
        qname = "DEPTH.TEST.Q"
        for i in range(3):
            self.adapter.put(qname, MQMessage.from_text(f"msg {i}"))
        assert self.adapter.queue_depths()[qname] == 3

    def test_from_ebcdic(self):
        codec = EbcdicCodec()
        raw = codec.encode("TRADE DATA")
        msg = MQMessage.from_ebcdic(raw, code_page="cp037")
        assert "TRADE DATA" in msg.payload_text

    def test_queue_full_raises(self):
        from zos_bridge.mq import MQQueue
        q = MQQueue(name="TINY.Q", max_depth=2)
        q.put(MQMessage.from_text("a"))
        q.put(MQMessage.from_text("b"))
        with pytest.raises(RuntimeError, match="MQRC_Q_FULL"):
            q.put(MQMessage.from_text("c"))


# ── RACF ──────────────────────────────────────────────────────────────────────

class TestRACF:
    def test_special_user_gets_alter(self):
        profile = RACFProfile("SYSADM", attributes=["SPECIAL"])
        acl = RACFAccessList("PAYROLL.MASTER", uacc=RACFPermission.NONE)
        assert acl.check(profile) == RACFPermission.ALTER

    def test_uacc_fallback(self):
        profile = RACFProfile("JDOE")
        acl = RACFAccessList("PUBLIC.DATA", uacc=RACFPermission.READ)
        assert acl.check(profile) == RACFPermission.READ

    def test_explicit_user_ace(self):
        profile = RACFProfile("JDOE")
        acl = RACFAccessList("SENSITIVE.DATA", uacc=RACFPermission.NONE)
        acl.permit("JDOE", RACFPermission.UPDATE)
        assert acl.check(profile) == RACFPermission.UPDATE

    def test_group_ace(self):
        profile = RACFProfile("ASMITH", groups=["FINGRP"])
        acl = RACFAccessList("FINANCE.DATA", uacc=RACFPermission.NONE)
        acl.permit("FINGRP", RACFPermission.READ, identity_type="GROUP")
        assert acl.check(profile) == RACFPermission.READ

    def test_user_ace_overrides_group(self):
        profile = RACFProfile("JDOE", groups=["FINGRP"])
        acl = RACFAccessList("PAYROLL.MASTER", uacc=RACFPermission.NONE)
        acl.permit("FINGRP", RACFPermission.READ, identity_type="GROUP")
        acl.permit("JDOE",   RACFPermission.ALTER)
        assert acl.check(profile) == RACFPermission.ALTER

    def test_revoke_ace(self):
        acl = RACFAccessList("SOME.DATA", uacc=RACFPermission.NONE)
        acl.permit("JDOE", RACFPermission.UPDATE)
        assert acl.revoke("JDOE") is True
        profile = RACFProfile("JDOE")
        assert acl.check(profile) == RACFPermission.NONE
