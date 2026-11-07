"""The one read-access filter every retrieval path uses (TECH-V2-ai-service §6.1, FR-25).

``allowed_cte()`` is the only place that writes this SQL. It is fully parameterised (no
f-strings over request data) and adds ``workspace_id = :wid`` next to RLS, so tenant isolation
holds even if a policy were dropped (ADR-005, two layers). A document without a
``document_access`` row, deleted, or never activated is never returned (fail closed).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

ROLES = ("OWNER", "ADMIN", "MEMBER")


@dataclass(frozen=True)
class Principal:
    """Who asks, from the access token: ``sub``, ``wid``, ``wrole``, ``wdept``."""

    user_id: UUID
    workspace_id: UUID
    role: str
    department_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"unknown workspace role {self.role!r}")


_ALLOWED = """allowed AS (
    SELECT da.document_id, da.active_version_id, da.title
      FROM rag.document_access da
     WHERE da.workspace_id = :wid
       AND da.deleted_at IS NULL
       AND da.active_version_id IS NOT NULL
       AND ( CAST(:wrole AS text) IN ('OWNER', 'ADMIN')
             OR da.visibility = 'WORKSPACE'
             OR (CAST(:wdept AS uuid) IS NOT NULL
                 AND CAST(:wdept AS uuid) = ANY (da.department_ids)) )
)"""


def allowed_cte() -> str:
    """``allowed (document_id, active_version_id, title)`` CTE body, to follow ``WITH``."""
    return _ALLOWED


def access_params(principal: Principal) -> dict[str, Any]:
    return {
        "wid": principal.workspace_id,
        "wrole": principal.role,
        "wdept": principal.department_id,
    }
