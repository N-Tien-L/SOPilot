"""Static checks on the feedback SQL: every joined or counted table filters by workspace (V2-13).

RLS is the first layer; CLAUDE.md constraint 4 requires the explicit ``workspace_id`` filter as the
second. These checks fail if a subquery or join loses it. The database suite covers behaviour.
"""
from __future__ import annotations

import re

from sopilot_ai.feedback import repository as repo


def _sql(stmt: object) -> str:
    return re.sub(r"\s+", " ", str(stmt))


def test_gap_list_counts_and_joins_filter_by_workspace() -> None:
    sql = _sql(repo._GAP_LIST)
    assert "d.workspace_id = :wid AND d.vote = -1" in sql  # downvotes subquery
    assert "d.workspace_id = :wid AND d.vote = 1" in sql  # upvotes subquery
    assert "u.workspace_id = :wid AND u.created_at < m.created_at" in sql  # question lookup
    assert "ON ks.message_id = m.id AND ks.workspace_id = :wid" in sql  # resolved status join


def test_gap_criterion_downvote_exists_filters_by_workspace() -> None:
    assert "d.message_id = m.id AND d.workspace_id = :wid AND d.vote = -1" in _sql(repo._IS_GAP)
