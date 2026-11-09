"""The QA pipeline as a chain of steps (TECH-V2-ai-service §7.1, V2-10).

Each step reads and writes one shared :class:`PipelineContext` and returns a :class:`Decision`:

- ``continue``: go to the next step;
- ``template``: answer with a fixed sentence, no LLM (``outcome = TEMPLATE``);
- ``refuse``: refuse with a reason (guard block, ``NO_EVIDENCE``, later ``OUT_OF_SCOPE``);
- ``clarify``: declared so a later ticket can add a "which one do you mean?" branch. **No step
  emits it in V2-10.**

The first step that does not return ``continue`` ends the chain. The full order is
:data:`STEP_ORDER`; this ticket's deterministic steps live in :mod:`sopilot_ai.qa.steps`, and the
retrieval, prompt, generation and post-processing steps are added with the API (milestones 2-3).
The ``OUT_OF_SCOPE`` hook of ``V2-27`` belongs to the refusal step that follows the retrieval
gate, never before it (D1).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from sopilot_ai.qa.guard import GuardResult
from sopilot_ai.qa.query_frame import QueryFrame
from sopilot_ai.qa.router import RouteResult, Stripped

# TECH-V2-ai-service §7.1, in execution order.
STEP_ORDER: tuple[str, ...] = (
    "quota",
    "input",
    "pii",
    "frame",
    "guard",
    "router",
    "meaningful_tokens",
    "rewrite",
    "retrieve_and_gate",
    "build_context",
    "build_prompt",
    "generate_and_stream",
    "postprocess_citations",
    "detect_self_refusal",
    "check_numbers",
)


class DecisionKind(StrEnum):
    CONTINUE = "continue"
    TEMPLATE = "template"
    REFUSE = "refuse"
    CLARIFY = "clarify"


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    outcome: str | None = None  # TEMPLATE | REFUSED_GUARD | REFUSED_NO_EVIDENCE | ...
    refusal_reason: str | None = None  # TECH §3.4; None when the table has no reason for it
    template_key: str | None = None  # key in templates.yaml
    template_values: dict[str, Any] = field(default_factory=dict)
    rule_id: str | None = None  # the rule that decided, for route / guard_events

    @property
    def stops(self) -> bool:
        return self.kind is not DecisionKind.CONTINUE


CONTINUE = Decision(DecisionKind.CONTINUE)


def template(key: str, *, reason: str | None = None, rule_id: str | None = None,
             **values: Any) -> Decision:
    return Decision(DecisionKind.TEMPLATE, "TEMPLATE", reason, key, values, rule_id)


def refuse(outcome: str, *, template_key: str | None = None, reason: str | None = None,
           rule_id: str | None = None, **values: Any) -> Decision:
    return Decision(DecisionKind.REFUSE, outcome, reason, template_key, values, rule_id)


@dataclass(frozen=True)
class GuardEvent:
    layer: str  # INPUT_BLOCK | INPUT_FLAG | OUTPUT_CANARY | OUTPUT_PROMPT_ECHO
    rule_id: str


@dataclass
class PipelineContext:
    """State shared by the steps of one question."""

    question: str  # as the user sent it
    lang_override: str | None = None
    max_question_chars: int = 1000
    followup_max_tokens: int | None = None
    # Looks up which of these lowercase tokens occur in the asker's own documents (reads
    # rag.chunk_terms through the access filter). Returns the subset that does.
    known_terms: Callable[[Sequence[str]], Awaitable[set[str]]] | None = None
    support_contact: str = ""  # shown with the self-harm sentence; configured by the owner

    text: str = ""  # NFC question, then PII-masked
    working_text: str = ""  # after stripping; what retrieval and the prompt use
    frame: QueryFrame | None = None
    guard: GuardResult | None = None
    stripped: Stripped | None = None
    route: RouteResult | None = None
    guard_events: list[GuardEvent] = field(default_factory=list)
    route_info: dict[str, Any] = field(default_factory=dict)  # -> messages.route
    checks: dict[str, Any] = field(default_factory=dict)  # -> messages.checks

    def record(self, layer: str, rule_id: str) -> None:
        self.guard_events.append(GuardEvent(layer, rule_id))


class Step(Protocol):
    name: str

    async def run(self, ctx: PipelineContext) -> Decision: ...


async def run_steps(steps: Sequence[Step], ctx: PipelineContext) -> Decision:
    """Run the steps in order; return the first decision that stops the chain, else ``CONTINUE``."""
    for step in steps:
        decision = await step.run(ctx)
        ctx.route_info.setdefault("steps", []).append(step.name)
        if decision.stops:
            ctx.route_info["decided_by"] = step.name
            return decision
    return CONTINUE
