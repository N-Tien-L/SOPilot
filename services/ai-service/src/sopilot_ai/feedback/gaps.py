"""Which answers count as a knowledge gap (TECH-V2-ai-service §7.6, owner D2 2026-10-21).

The criteria are constants so the SQL in ``repository.py`` is built from the same sets; nothing
else in the code states them.
"""
from __future__ import annotations

# Refusals that mean "the workspace has no document for this": the admin should add one.
GAP_REFUSAL_REASONS = ("NO_EVIDENCE", "GENERATOR_NOT_FOUND")
# Answers that are never a gap, whatever the votes: a scope refusal, invalid input, a fixed
# template or a guard refusal are the system working as designed.
EXCLUDED_OUTCOMES = ("TEMPLATE", "REFUSED_GUARD", "QUOTA_EXCEEDED")
EXCLUDED_REFUSAL_REASONS = ("OUT_OF_SCOPE", "INPUT_INVALID")
DOWNVOTE = -1
