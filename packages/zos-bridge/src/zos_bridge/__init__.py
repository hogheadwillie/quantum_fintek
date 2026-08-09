"""QuantumFintek IBM z/OS bridge package.

Provides pure-Python utilities for interoperating with IBM Z-series mainframes:
- EBCDIC ↔ UTF-8 transcoding (IBM-037, IBM-1047, IBM-1140 code pages)
- MVS dataset record-format parsing (F, FB, V, VB, U)
- RACF-style access control list model
- MQI-compatible message envelope (IBM MQ stub)
- JCL job submission and status model
- LPAR connection configuration
"""

from .codec import EbcdicCodec, CodePage
from .dataset import DatasetRecord, RecordFormat, DatasetParser
from .racf import RACFProfile, RACFPermission, RACFAccessList
from .mq import MQMessage, MQQueue, MQBridgeAdapter
from .jcl import JCLJob, JCLStep, JobStatus, JCLBuilder
from .lpar import LPARConnection, LPARConfig

__all__ = [
    "EbcdicCodec", "CodePage",
    "DatasetRecord", "RecordFormat", "DatasetParser",
    "RACFProfile", "RACFPermission", "RACFAccessList",
    "MQMessage", "MQQueue", "MQBridgeAdapter",
    "JCLJob", "JCLStep", "JobStatus", "JCLBuilder",
    "LPARConnection", "LPARConfig",
]
