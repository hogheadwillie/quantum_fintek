"""RACF-style Resource Access Control Facility model.

Models the RACF security constructs used on IBM z/OS:
  - User profiles with group memberships
  - Dataset/resource profiles with access lists (UACC + individual ACEs)
  - Permission levels: NONE, READ, UPDATE, CONTROL, ALTER
  - ACCESS CHECK: determines effective permission for a user on a resource
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class RACFPermission(IntEnum):
    NONE    = 0
    READ    = 1
    UPDATE  = 2
    CONTROL = 3
    ALTER   = 4


@dataclass
class RACFProfile:
    """Represents a RACF user profile."""

    userid: str                        # uppercase, max 8 chars (IBM standard)
    name: str = ""
    groups: list[str] = field(default_factory=list)   # group memberships
    attributes: list[str] = field(default_factory=list)  # e.g. SPECIAL, AUDITOR, OPERATIONS
    active: bool = True

    def __post_init__(self) -> None:
        self.userid = self.userid.upper()[:8]
        self.groups = [g.upper() for g in self.groups]
        self.attributes = [a.upper() for a in self.attributes]

    @property
    def is_special(self) -> bool:
        """SPECIAL attribute ≈ RACF superuser."""
        return "SPECIAL" in self.attributes

    @property
    def is_auditor(self) -> bool:
        return "AUDITOR" in self.attributes


@dataclass
class AccessControlEntry:
    """A single ACE on a resource: user or group + permission level."""
    identity: str         # USERID or GROUPNAME (uppercase)
    permission: RACFPermission
    identity_type: str = "USER"   # USER | GROUP

    def __post_init__(self) -> None:
        self.identity = self.identity.upper()
        self.identity_type = self.identity_type.upper()


@dataclass
class RACFAccessList:
    """RACF dataset / general resource profile with an access list.

    Access resolution follows RACF rules:
    1. SPECIAL attribute → ALTER
    2. Explicit USER ACE (highest wins if multiple)
    3. GROUP ACE (highest of all matching groups)
    4. Universal Access (UACC)
    5. Default: NONE
    """

    resource_name: str              # e.g. "PAYROLL.MASTER.DATA"
    resource_class: str = "DATASET" # DATASET | FACILITY | PROGRAM | …
    uacc: RACFPermission = RACFPermission.NONE
    acl: list[AccessControlEntry] = field(default_factory=list)
    owner: str = ""

    # ── mutation ──────────────────────────────────────────────────────────────

    def permit(
        self,
        identity: str,
        permission: RACFPermission,
        identity_type: str = "USER",
    ) -> None:
        """Add or update an ACE for the given identity."""
        identity = identity.upper()
        for ace in self.acl:
            if ace.identity == identity and ace.identity_type == identity_type.upper():
                ace.permission = permission
                return
        self.acl.append(AccessControlEntry(identity, permission, identity_type))

    def revoke(self, identity: str, identity_type: str = "USER") -> bool:
        identity = identity.upper()
        before = len(self.acl)
        self.acl = [a for a in self.acl if not (a.identity == identity and a.identity_type == identity_type.upper())]
        return len(self.acl) < before

    # ── access check ─────────────────────────────────────────────────────────

    def check(self, profile: RACFProfile) -> RACFPermission:
        """Return the effective permission for *profile* on this resource."""
        if profile.is_special:
            return RACFPermission.ALTER

        # Explicit USER ACE
        user_perm: Optional[RACFPermission] = None
        for ace in self.acl:
            if ace.identity_type == "USER" and ace.identity == profile.userid:
                user_perm = ace.permission
                break
        if user_perm is not None:
            return user_perm

        # Best GROUP ACE
        group_perm: Optional[RACFPermission] = None
        for ace in self.acl:
            if ace.identity_type == "GROUP" and ace.identity in profile.groups:
                if group_perm is None or ace.permission > group_perm:
                    group_perm = ace.permission
        if group_perm is not None:
            return group_perm

        return self.uacc
