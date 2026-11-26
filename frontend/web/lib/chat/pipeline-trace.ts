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
  StageChunkBody,
  StageChunkRef,
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
  { id: 'input_pii', index: 1, title: 'Input and personal data masking', subtitle: 'Checking length and personal data' },
  { id: 'guard_rule', index: 2, title: 'Guardrails and rule router', subtitle: 'Safety rules and templates' },
  { id: 'classify_route', index: 3, title: 'Question type and routing', subtitle: 'Language and classifier routing' },
  { id: 'rewrite_translate', index: 4, title: 'Rewrite and translation', subtitle: 'Standalone rewrite and cross-lingual query' },
  { id: 'retrieve_dense', index: 5, title: 'Meaning search (dense)', subtitle: 'Embedding cosine similarity search' },
  { id: 'retrieve_sparse', index: 6, title: 'Keyword search (BM25)', subtitle: 'Lexical keyword matching' },
  { id: 'retrieve_rrf', index: 7, title: 'Merge results (RRF)', subtitle: 'Reciprocal rank fusion and doc-code boost' },
  { id: 'retrieve_rerank', index: 8, title: 'Reranker and relevance gate', subtitle: 'Cross-encoder scoring and threshold gate' },
  { id: 'context_prompt', index: 9, title: 'Context and prompt', subtitle: 'Section expansion and prompt assembly' },
  { id: 'llm_generate', index: 10, title: 'Answer generation', subtitle: 'Reasoning and streaming answer' },
  { id: 'post_checks', index: 11, title: 'Citation and number checks', subtitle: 'Output guard, citations and numbers' },
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
    stageChunks: {},
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

function extractStageChunks(detail: Record<string, unknown> | undefined): Record<string, StageChunkBody> | null {
  if (!detail || typeof detail.stageChunks !== 'object' || detail.stageChunks === null || Array.isArray(detail.stageChunks)) {
    return null;
  }
  return detail.stageChunks as Record<string, StageChunkBody>;
}

function extractPromptMessages(detail: Record<string, unknown> | undefined): PromptMessageTrace[] | null {
  if (!detail || !Array.isArray(detail.messages)) return null;
  return detail.messages as PromptMessageTrace[];
}

function parseStageRefs(raw: unknown): StageChunkRef[] {
  if (!Array.isArray(raw)) return [];
  const out: StageChunkRef[] = [];
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    if (typeof r.chunkId !== 'string' || typeof r.score !== 'number') continue;
    out.push({
      chunkId: r.chunkId,
      rank: typeof r.rank === 'number' ? r.rank : out.length + 1,
      score: r.score,
      source: r.source === 'orig' || r.source === 'alt' || r.source === 'both' ? r.source : undefined,
      docCodeMatch: r.docCodeMatch === true,
      inPool: r.inPool === true,
    });
  }
  return out;
}

/**
 * Hydrate a retrieval stage's own candidate list (dense, bm25, or rrf) from its `detail.items`
 * using `trace.stageChunks` (with fallback to `trace.chunks` for pre-upgrade stored traces).
 */
export function resolveStageChunks(
  kind: 'dense' | 'bm25' | 'rrf',
  trace: PipelineTrace,
  stepDetail?: Record<string, unknown>,
): RetrievedChunkTrace[] {
  const refs = parseStageRefs(stepDetail?.items);
  if (refs.length === 0) {
    if (kind === 'dense') return trace.chunks.filter((c) => c.denseScore !== null);
    if (kind === 'bm25') return trace.chunks.filter((c) => c.bm25Score !== null);
    return trace.chunks.filter((c) => c.fusionScore !== null);
  }

  const catalog = trace.stageChunks ?? {};
  const byChunkId = new Map<string, RetrievedChunkTrace>();
  const inContextIds = new Set<string>();
  for (const c of trace.chunks) {
    byChunkId.set(c.chunkId, c);
    if (c.inContext) inContextIds.add(c.chunkId);
  }

  const denseScores = new Map<string, number>();
  const bm25Scores = new Map<string, number>();
  if (kind === 'rrf') {
    const denseStep = trace.steps.find((s) => s.step === 'retrieve_dense');
    for (const r of parseStageRefs(denseStep?.detail?.items)) denseScores.set(r.chunkId, r.score);
    const sparseStep = trace.steps.find((s) => s.step === 'retrieve_sparse');
    for (const r of parseStageRefs(sparseStep?.detail?.items)) bm25Scores.set(r.chunkId, r.score);
  }

  const resolved: RetrievedChunkTrace[] = [];
  for (const ref of refs) {
    const body = catalog[ref.chunkId] ?? byChunkId.get(ref.chunkId);
    if (!body) continue;
    resolved.push({
      rank: ref.rank,
      chunkId: body.chunkId,
      documentId: body.documentId,
      versionId: body.versionId,
      title: body.title,
      sectionPath: body.sectionPath,
      page: body.page,
      chunkType: body.chunkType,
      tokenCount: body.tokenCount,
      denseScore: kind === 'dense' ? ref.score : kind === 'rrf' ? (denseScores.get(ref.chunkId) ?? null) : null,
      bm25Score: kind === 'bm25' ? ref.score : kind === 'rrf' ? (bm25Scores.get(ref.chunkId) ?? null) : null,
      fusionScore: kind === 'rrf' ? ref.score : null,
      rerankScore: null,
      docCodeMatch: Boolean(ref.docCodeMatch),
      inContext: inContextIds.has(ref.chunkId),
      preview: body.preview,
      content: body.content,
      source: ref.source,
      inPool: ref.inPool,
    });
  }
  return resolved;
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
      const stageChunks =
        event.step === 'retrieve_and_gate'
          ? (extractStageChunks(event.detail) ?? trace.stageChunks)
          : trace.stageChunks;
      const promptMessages =
        event.step === 'build_prompt' ? (extractPromptMessages(event.detail) ?? trace.promptMessages) : trace.promptMessages;
      return { ...trace, steps, chunks, stageChunks, promptMessages };
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
