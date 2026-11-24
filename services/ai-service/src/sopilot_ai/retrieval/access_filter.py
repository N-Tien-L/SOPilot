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


# One predicate, used by both CTEs below, so "readable" has a single definition.
_READABLE = """da.deleted_at IS NULL
       AND da.active_version_id IS NOT NULL
       AND ( CAST(:wrole AS text) IN ('OWNER', 'ADMIN')
             OR da.visibility = 'WORKSPACE'
             OR (CAST(:wdept AS uuid) IS NOT NULL
                 AND CAST(:wdept AS uuid) = ANY (da.department_ids)) )"""

_ALLOWED = f"""allowed AS (
    SELECT da.document_id, da.active_version_id, da.title
      FROM rag.document_access da
     WHERE da.workspace_id = :wid
       AND {_READABLE}
)"""

# Same predicate, but every document of the workspace with the reason a citation may be hidden
# (TECH-V2-ai-service §7.5): used only to re-read a stored conversation, never to retrieve.
_CITED_ACCESS = f"""cited_access AS (
    SELECT da.document_id, da.active_version_id, da.title,
           da.deleted_at IS NOT NULL AS deleted,
           ({_READABLE}) AS readable
      FROM rag.document_access da
     WHERE da.workspace_id = :wid
)"""


def allowed_cte() -> str:
    """``allowed (document_id, active_version_id, title)`` CTE body, to follow ``WITH``."""
    return _ALLOWED


def cited_access_cte() -> str:
    """``cited_access (document_id, active_version_id, title, deleted, readable)`` CTE body.

    ``readable`` is exactly the ``allowed`` predicate. A document that has no row at all is
    absent from the CTE; callers treat that as deleted (fail closed).
    """
    return _CITED_ACCESS


def access_params(principal: Principal) -> dict[str, Any]:
    return {
        "wid": principal.workspace_id,
        "wrole": principal.role,
        "wdept": principal.department_id,
    }
