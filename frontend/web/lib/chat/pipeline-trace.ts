// Pure state reducer & 8-stage view aggregator for the Real-time Query Pipeline Inspector.
// Works identically on live SSE streams and persisted traces from GET .../trace.

import type {
  PipelineDecision,
  PipelineStageId,
  PipelineStepEntry,
  PipelineStepStatus,
  PipelineTrace,
  PromptMessageTrace,
  RetrievedChunkTrace,
  StreamEvent,
} from '@/lib/api/types';
import type { StreamEnd } from '@/lib/sse/stream';

export interface StageDefinition {
  id: PipelineStageId;
  index: number;
  title: string;
  subtitle: string;
}

export const PIPELINE_STAGES: readonly StageDefinition[] = [
  { id: 'input_pii', index: 1, title: 'Input, Quota & PII Masking', subtitle: 'Validation, quota & PII redaction' },
  { id: 'guard_rule', index: 2, title: 'Guardrails & Rule Router', subtitle: 'Safety rules, word stripping & templates' },
  { id: 'classify_route', index: 3, title: 'Query Frame, Classify & Routing', subtitle: 'Signals, Semantic & SetFit routing' },
  { id: 'rewrite_translate', index: 4, title: 'Query Rewrite & Translation', subtitle: 'Standalone rewrite & cross-lingual query' },
  { id: 'retrieve_dense', index: 5, title: 'Dense Vector Search', subtitle: 'Semantic embedding cosine search (pgvector)' },
  { id: 'retrieve_sparse', index: 6, title: 'Sparse Lexical Search (BM25)', subtitle: 'Exact keyword & term-frequency matching' },
  { id: 'retrieve_rrf', index: 7, title: 'RRF Fusion & Boost', subtitle: 'Reciprocal rank fusion & doc-code boost' },
  { id: 'retrieve_rerank', index: 8, title: 'Reranker & Relevance Gate', subtitle: 'Cross-encoder scoring, RLS & gate threshold' },
  { id: 'context_prompt', index: 9, title: 'Context & Final Fusion Prompt', subtitle: 'Section expansion, token budget & prompt' },
  { id: 'llm_generate', index: 10, title: 'LLM Processing (Modal)', subtitle: 'Streaming reasoning & answer generation' },
  { id: 'post_checks', index: 11, title: 'Post-checks & Final Response', subtitle: 'OutputGuard, citations, self-refusal & numbers' },
] as const;

export interface AggregatedStage {
  def: StageDefinition;
  status: PipelineStepStatus;
  durationMs: number | null;
  summary: string | null;
  decision: PipelineDecision | null;
  steps: PipelineStepEntry[];
  byStep: Record<string, PipelineStepEntry>;
}

export function createInitialTrace(question: string): PipelineTrace {
  return {
    version: 1,
    messageId: null,
    conversationId: null,
    question,
    mode: 'hybrid',
    lang: 'vi',
    outcome: null,
    refusalReason: null,
    totalMs: null,
    disclaimers: [],
    reconstructed: false,
    hidden: false,
    hiddenReason: null,
    steps: [],
    chunks: [],
    promptMessages: null,
    live: true,
  };
}

function upsertStep(steps: PipelineStepEntry[], next: PipelineStepEntry): PipelineStepEntry[] {
  const idx = steps.findIndex((s) => s.step === next.step);
  if (idx === -1) return [...steps, next];
  const prev = steps[idx];
  const merged: PipelineStepEntry = {
    ...prev,
    ...next,
    detail: next.detail ? { ...(prev.detail ?? {}), ...next.detail } : prev.detail,
  };
  const copy = steps.slice();
  copy[idx] = merged;
  return copy;
}

function extractChunks(detail: Record<string, unknown> | undefined): RetrievedChunkTrace[] | null {
  if (!detail || !Array.isArray(detail.chunks)) return null;
  return detail.chunks as RetrievedChunkTrace[];
}

function extractPromptMessages(detail: Record<string, unknown> | undefined): PromptMessageTrace[] | null {
  if (!detail || !Array.isArray(detail.messages)) return null;
  return detail.messages as PromptMessageTrace[];
}

export function reducePipelineTrace(trace: PipelineTrace, event: StreamEvent): PipelineTrace {
  switch (event.type) {
    case 'meta':
      return {
        ...trace,
        conversationId: event.conversationId,
        messageId: event.messageId,
        mode: event.mode || trace.mode,
        lang: event.lang || trace.lang,
      };
    case 'step': {
      const entry: PipelineStepEntry = {
        step: event.step,
        stage: event.stage,
        status: event.status,
        ...(event.durationMs !== undefined ? { durationMs: event.durationMs } : {}),
        ...(event.decision !== undefined ? { decision: event.decision } : {}),
        ...(event.summary !== undefined ? { summary: event.summary } : {}),
        ...(event.detail !== undefined ? { detail: event.detail } : {}),
      };
      const steps = upsertStep(trace.steps, entry);
      const chunks = event.step === 'retrieve_and_gate' ? (extractChunks(event.detail) ?? trace.chunks) : trace.chunks;
      const promptMessages =
        event.step === 'build_prompt' ? (extractPromptMessages(event.detail) ?? trace.promptMessages) : trace.promptMessages;
      return { ...trace, steps, chunks, promptMessages };
    }
    case 'reasoning': {
      const existing = trace.steps.find((s) => s.step === 'generate_and_stream');
      const prevChars = typeof existing?.detail?.reasoningChars === 'number' ? existing.detail.reasoningChars : 0;
      const steps = upsertStep(trace.steps, {
        step: 'generate_and_stream',
        stage: 'llm_generate',
        status: 'running',
        summary: existing?.detail?.model
          ? `Thinking with ${String(existing.detail.model)}…`
          : 'Model is thinking…',
        detail: {
          streamingPhase: 'thinking',
          reasoningChars: prevChars + event.text.length,
        },
      });
      return { ...trace, steps };
    }
    case 'reasoning_done': {
      const existing = trace.steps.find((s) => s.step === 'generate_and_stream');
      const steps = upsertStep(trace.steps, {
        step: 'generate_and_stream',
        stage: 'llm_generate',
        status: 'running',
        summary: existing?.detail?.model
          ? `Streaming answer from ${String(existing.detail.model)}…`
          : 'Streaming answer…',
        detail: {
          streamingPhase: 'answering',
          reasoningMs: event.durationMs,
        },
      });
      return { ...trace, steps };
    }
    case 'delta': {
      const existing = trace.steps.find((s) => s.step === 'generate_and_stream');
      if (!existing || existing.status !== 'running') return trace;
      const prevChars = typeof existing.detail?.answerChars === 'number' ? existing.detail.answerChars : 0;
      const steps = upsertStep(trace.steps, {
        step: 'generate_and_stream',
        stage: 'llm_generate',
        status: 'running',
        detail: {
          streamingPhase: 'answering',
          answerChars: prevChars + event.text.length,
        },
      });
      return { ...trace, steps };
    }
    case 'done': {
      const totalMs = trace.steps.reduce((acc, s) => acc + (typeof s.durationMs === 'number' ? s.durationMs : 0), 0);
      return {
        ...trace,
        outcome: event.outcome,
        refusalReason: event.refusalReason,
        totalMs: trace.totalMs ?? totalMs,
        live: false,
      };
    }
    case 'error':
      return {
        ...trace,
        outcome: event.code === 'QUOTA_EXCEEDED' ? 'QUOTA_EXCEEDED' : 'ERROR',
        live: false,
      };
    default:
      return trace;
  }
}

export function finalizeAbortedTrace(trace: PipelineTrace, end: StreamEnd): PipelineTrace {
  if (end.status === 'done') return { ...trace, live: false };
  const steps = trace.steps.map((s) =>
    s.status === 'running'
      ? {
          ...s,
          status: 'error' as PipelineStepStatus,
          summary: end.status === 'cancelled' ? 'Stopped by user' : end.status === 'error' ? end.message : 'Connection interrupted',
        }
      : s,
  );
  return {
    ...trace,
    steps,
    outcome: trace.outcome ?? (end.status === 'cancelled' ? 'CANCELLED' : 'ERROR'),
    live: false,
  };
}

/**
 * Groups flat step entries into the 8 ordered UI stages.
 * Handles early stops (marking unreached stages `skipped`) and `frame` running before `guard`.
 */
export function aggregateStages(trace: PipelineTrace): AggregatedStage[] {
  const isFinished = !trace.live;
  let stopped = false;

  return PIPELINE_STAGES.map((def) => {
    const entries = trace.steps.filter((s) => s.stage === def.id);
    const byStep: Record<string, PipelineStepEntry> = {};
    for (const e of entries) byStep[e.step] = e;

    const decision = entries.find((e) => e.decision != null)?.decision ?? null;
    const hasError = entries.some((e) => e.status === 'error');
    const hasBlocked = entries.some((e) => e.status === 'blocked');
    const hasRunning = entries.some((e) => e.status === 'running');
    const hasPassed = entries.some((e) => e.status === 'passed');

    let status: PipelineStepStatus;
    if (entries.length === 0) {
      status = stopped || isFinished ? 'skipped' : 'pending';
    } else if (hasError) {
      status = 'error';
    } else if (hasBlocked) {
      status = 'blocked';
    } else if (hasRunning) {
      status = 'running';
    } else if (stopped && def.id === 'classify_route' && entries.length === 1 && entries[0].step === 'frame') {
      // FrameStep ran before GuardStep blocked; classifier/semantic router did not run.
      status = 'passed';
    } else if (hasPassed) {
      status = 'passed';
    } else {
      status = 'pending';
    }

    if (status === 'blocked' || status === 'error') {
      stopped = true;
    }

    const durations = entries.map((e) => e.durationMs).filter((d): d is number => typeof d === 'number');
    const durationMs = durations.length > 0 ? durations.reduce((a, b) => a + b, 0) : null;

    // Pick the most informative summary: blocked/error > running > last completed entry
    const primary =
      entries.find((e) => e.status === 'error' || e.status === 'blocked') ??
      entries.find((e) => e.status === 'running') ??
      entries[entries.length - 1];

    return {
      def,
      status,
      durationMs,
      summary: primary?.summary ?? (status === 'skipped' ? 'Skipped' : null),
      decision,
      steps: entries,
      byStep,
    };
  });
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return '';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}
