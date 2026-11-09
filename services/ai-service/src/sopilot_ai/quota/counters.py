"""Question counters (FR-09, TECH-V2-ai-service §7.4).

Both limits default to ``0`` = off, and then nothing here reads or writes a table. When a limit is
on, a question is *reserved* (counted atomically against the limit) at the start of the request and
*released* when the outcome is one that does not count: ``TEMPLATE``, ``REFUSED_GUARD`` and
``ERROR`` (the LLM was unavailable). The per-user counter has ``workspace_id`` and RLS, so it runs
in ``tenant_tx``; ``rag.system_usage`` has neither and runs in ``system_tx``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from sopilot_ai.db.engine import system_tx, tenant_tx

# Outcomes that do not use a question of the quota.
FREE_OUTCOMES = frozenset({"TEMPLATE", "REFUSED_GUARD", "ERROR", "QUOTA_EXCEEDED"})

_RESERVE_USER = text("""
INSERT INTO rag.usage_counters (workspace_id, user_id, day, questions)
VALUES (:wid, :uid, :day, 1)
ON CONFLICT (workspace_id, user_id, day)
DO UPDATE SET questions = rag.usage_counters.questions + 1
        WHERE rag.usage_counters.questions < :limit
RETURNING questions
""")
_RELEASE_USER = text("""
UPDATE rag.usage_counters SET questions = greatest(questions - 1, 0)
 WHERE workspace_id = :wid AND user_id = :uid AND day = :day
""")
_RESERVE_SYSTEM = text("""
INSERT INTO rag.system_usage (day, questions) VALUES (:day, 1)
ON CONFLICT (day) DO UPDATE SET questions = rag.system_usage.questions + 1
        WHERE rag.system_usage.questions < :limit
RETURNING questions
""")
_RELEASE_SYSTEM = text("""
UPDATE rag.system_usage SET questions = greatest(questions - 1, 0) WHERE day = :day
""")


class QuotaState(StrEnum):
    OFF = "off"  # both limits are 0: nothing was counted
    RESERVED = "reserved"
    USER_EXCEEDED = "user"
    SYSTEM_EXCEEDED = "system"


@dataclass(frozen=True)
class Reservation:
    state: QuotaState
    day: date | None = None
    user_used: int | None = None
    user_limit: int = 0
    user_reserved: bool = False
    system_reserved: bool = False
    released: bool = False  # given back after an outcome that does not count

    @property
    def allowed(self) -> bool:
        return self.state in (QuotaState.OFF, QuotaState.RESERVED)

    @property
    def questions_left(self) -> int | None:
        """``done.usage.questionsLeftToday``: ``None`` when the per-user limit is off."""
        if not self.user_limit or self.user_used is None:
            return None
        used = self.user_used - (1 if self.released and self.user_reserved else 0)
        return max(self.user_limit - used, 0)


class QuotaCounter:
    def __init__(self, engine: AsyncEngine, *, per_user_day: int = 0, system_day: int = 0) -> None:
        self.engine = engine
        self.per_user_day = per_user_day
        self.system_day = system_day

    @property
    def enabled(self) -> bool:
        return bool(self.per_user_day or self.system_day)

    async def reserve(self, workspace_id: UUID, user_id: UUID, day: date) -> Reservation:
        if not self.enabled:
            return Reservation(QuotaState.OFF)
        used: int | None = None
        user_reserved = False
        if self.per_user_day:
            async with tenant_tx(self.engine, workspace_id, user_id) as conn:
                row = (await conn.execute(_RESERVE_USER, {
                    "wid": workspace_id, "uid": user_id, "day": day,
                    "limit": self.per_user_day})).first()
            if row is None:
                return Reservation(QuotaState.USER_EXCEEDED, day, user_limit=self.per_user_day)
            used, user_reserved = int(row.questions), True
        if self.system_day:
            async with system_tx(self.engine) as conn:
                row = (await conn.execute(_RESERVE_SYSTEM, {
                    "day": day, "limit": self.system_day})).first()
            if row is None:
                if user_reserved:  # the system ceiling stopped it: give the user's question back
                    await self._release_user(workspace_id, user_id, day)
                return Reservation(QuotaState.SYSTEM_EXCEEDED, day,
                                   user_limit=self.per_user_day)
        return Reservation(QuotaState.RESERVED, day, used, self.per_user_day, user_reserved,
                           bool(self.system_day))

    async def release(self, workspace_id: UUID, user_id: UUID,
                      reservation: Reservation) -> Reservation:
        """Give a reserved question back; returns the reservation with the new count."""
        if (reservation.state is not QuotaState.RESERVED or reservation.day is None
                or reservation.released):
            return reservation
        if reservation.user_reserved:
            await self._release_user(workspace_id, user_id, reservation.day)
        if reservation.system_reserved:
            async with system_tx(self.engine) as conn:
                await conn.execute(_RELEASE_SYSTEM, {"day": reservation.day})
        return replace(reservation, released=True)

    async def _release_user(self, workspace_id: UUID, user_id: UUID, day: date) -> None:
        async with tenant_tx(self.engine, workspace_id, user_id) as conn:
            await conn.execute(_RELEASE_USER, {"wid": workspace_id, "uid": user_id, "day": day})
