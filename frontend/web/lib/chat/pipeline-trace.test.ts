import { describe, expect, it } from 'vitest';
import type { StreamEvent } from '@/lib/api/types';
import { decodeStreamEvent } from '@/lib/sse/parser';
import {
  aggregateStages,
  createInitialTrace,
  finalizeAbortedTrace,
  reducePipelineTrace,
  resolveStageChunks,
} from './pipeline-trace';

describe('decodeStreamEvent for step events', () => {
  it('decodes a valid step event with detail and decision', () => {
    const ev = decodeStreamEvent({
      event: 'step',
      data: JSON.stringify({
        step: 'guard',
        stage: 'guard_rule',
        status: 'blocked',
        durationMs: 2,
        decision: { kind: 'refuse', outcome: 'REFUSED_GUARD', reason: null, ruleId: 'guard.injection' },
        summary: 'Blocked by guard (guard.injection)',
        detail: { blocked: true, blockedRule: 'guard.injection' },
      }),
    });
    expect(ev).toMatchObject({
      type: 'step',
      step: 'guard',
      stage: 'guard_rule',
      status: 'blocked',
      durationMs: 2,
    });
  });

  it('returns null when step event is missing required fields', () => {
    expect(decodeStreamEvent({ event: 'step', data: JSON.stringify({ step: 'guard' }) })).toBeNull();
  });
});

describe('reducePipelineTrace & aggregateStages', () => {
  const run = (events: StreamEvent[]) => events.reduce(reducePipelineTrace, createInitialTrace('Test question'));

  it('tracks an 11-stage happy path and extracts chunks & promptMessages', () => {
    const trace = run([
      { type: 'meta', conversationId: 'c1', messageId: 'm1', mode: 'hybrid_rerank', lang: 'en' },
      { type: 'step', step: 'input', stage: 'input_pii', status: 'passed', durationMs: 1, summary: 'Valid' },
      { type: 'step', step: 'pii', stage: 'input_pii', status: 'passed', durationMs: 2, summary: 'Clean' },
      { type: 'step', step: 'frame', stage: 'classify_route', status: 'passed', durationMs: 3, summary: 'Frame' },
      { type: 'step', step: 'guard', stage: 'guard_rule', status: 'passed', durationMs: 1, summary: 'Clean' },
      { type: 'step', step: 'rewrite', stage: 'rewrite_translate', status: 'passed', durationMs: 0, summary: 'None' },
      { type: 'step', step: 'retrieve_dense', stage: 'retrieve_dense', status: 'passed', durationMs: 18, summary: '8 dense' },
      { type: 'step', step: 'retrieve_sparse', stage: 'retrieve_sparse', status: 'passed', durationMs: 9, summary: '8 BM25' },
      { type: 'step', step: 'retrieve_rrf', stage: 'retrieve_rrf', status: 'passed', durationMs: 2, summary: 'Fused 8' },
      {
        type: 'step',
        step: 'retrieve_and_gate',
        stage: 'retrieve_rerank',
        status: 'passed',
        durationMs: 85,
        summary: '1 hit passed',
        detail: {
          chunks: [
            {
              rank: 1,
              chunkId: 'ch1',
              documentId: 'd1',
              versionId: 'v1',
              title: 'Ops SOP',
              sectionPath: ['1'],
              page: 1,
              chunkType: 'SECTION',
              tokenCount: 100,
              denseScore: 0.9,
              bm25Score: 3.1,
              fusionScore: 0.03,
              rerankScore: 0.85,
              docCodeMatch: false,
              inContext: true,
              preview: 'SLA is 24h',
              content: 'SLA is 24h full',
            },
          ],
        },
      },
      {
        type: 'step',
        step: 'build_prompt',
        stage: 'context_prompt',
        status: 'passed',
        durationMs: 1,
        summary: 'Prompt ready',
        detail: {
          messages: [
            { role: 'system', content: 'Rules [REDACTED_CANARY]' },
            { role: 'user', content: 'Question' },
          ],
        },
      },
      { type: 'step', step: 'generate_and_stream', stage: 'llm_generate', status: 'running', summary: 'Streaming' },
      { type: 'reasoning', text: 'Thinking...' },
      { type: 'reasoning_done', durationMs: 400 },
      { type: 'delta', text: 'Answer [1].' },
      { type: 'step', step: 'generate_and_stream', stage: 'llm_generate', status: 'passed', durationMs: 900, summary: 'Done' },
      { type: 'step', step: 'postprocess_citations', stage: 'post_checks', status: 'passed', durationMs: 1, summary: '1 citation' },
      { type: 'done', finalText: 'Answer [1].', outcome: 'ANSWERED', refusalReason: null, warnings: [], usage: null },
    ]);

    expect(trace.live).toBe(false);
    expect(trace.chunks).toHaveLength(1);
    expect(trace.promptMessages).toHaveLength(2);
    const stages = aggregateStages(trace);
    expect(stages).toHaveLength(11);
    expect(stages.every((s) => s.status === 'passed')).toBe(true);
    expect(stages[0].durationMs).toBe(3);
  });

  it('marks remaining stages skipped when GuardStep blocks early', () => {
    const trace = run([
      { type: 'meta', conversationId: 'c1', messageId: 'm2', mode: 'hybrid', lang: 'en' },
      { type: 'step', step: 'input', stage: 'input_pii', status: 'passed', durationMs: 1 },
      { type: 'step', step: 'pii', stage: 'input_pii', status: 'passed', durationMs: 1 },
      { type: 'step', step: 'frame', stage: 'classify_route', status: 'passed', durationMs: 2 },
      {
        type: 'step',
        step: 'guard',
        stage: 'guard_rule',
        status: 'blocked',
        durationMs: 1,
        decision: { kind: 'refuse', outcome: 'REFUSED_GUARD', reason: null, ruleId: 'guard.injection' },
        summary: 'Blocked by guard',
      },
      { type: 'done', finalText: 'Blocked.', outcome: 'REFUSED_GUARD', refusalReason: null, warnings: [], usage: null },
    ]);

    const stages = aggregateStages(trace);
    expect(stages[0].status).toBe('passed');
    expect(stages[1].status).toBe('blocked');
    expect(stages[2].status).toBe('passed'); // frame ran before guard
    expect(stages.slice(3).every((s) => s.status === 'skipped')).toBe(true);
  });

  it('finalizes a running stage on user cancellation', () => {
    const live = run([
      { type: 'step', step: 'retrieve_and_gate', stage: 'retrieve_rerank', status: 'running' },
    ]);
    const stopped = finalizeAbortedTrace(live, { status: 'cancelled' });
    expect(stopped.live).toBe(false);
    expect(stopped.outcome).toBe('CANCELLED');
    const stages = aggregateStages(stopped);
    expect(stages[7].status).toBe('error');
    expect(stages[7].summary).toBe('Stopped by user');
  });

  it('resolves independent per-stage candidate lists for dense, sparse and RRF', () => {
    const makeBody = (id: string, title: string) => ({
      chunkId: id,
      documentId: `doc-${id}`,
      versionId: `ver-${id}`,
      title,
      sectionPath: ['1'],
      page: 1,
      chunkType: 'SECTION',
      tokenCount: 80,
      preview: `Preview ${id}`,
      content: `Content ${id}`,
    });
    const trace = run([
      {
        type: 'step',
        step: 'retrieve_dense',
        stage: 'retrieve_dense',
        status: 'passed',
        durationMs: 12,
        detail: {
          items: [
            { chunkId: 'd-only', rank: 1, score: 0.91, source: 'orig' },
            { chunkId: 'shared', rank: 2, score: 0.77, source: 'both' },
          ],
        },
      },
      {
        type: 'step',
        step: 'retrieve_sparse',
        stage: 'retrieve_sparse',
        status: 'passed',
        durationMs: 8,
        detail: {
          items: [
            { chunkId: 's-only', rank: 1, score: 11.4, source: 'orig' },
            { chunkId: 'shared', rank: 2, score: 6.2, source: 'alt' },
          ],
        },
      },
      {
        type: 'step',
        step: 'retrieve_rrf',
        stage: 'retrieve_rrf',
        status: 'passed',
        durationMs: 2,
        detail: {
          items: [
            { chunkId: 'shared', rank: 1, score: 0.0322, docCodeMatch: true, inPool: true },
            { chunkId: 'd-only', rank: 2, score: 0.0163, docCodeMatch: false, inPool: false },
            { chunkId: 's-only', rank: 3, score: 0.0163, docCodeMatch: false, inPool: false },
          ],
        },
      },
      {
        type: 'step',
        step: 'retrieve_and_gate',
        stage: 'retrieve_rerank',
        status: 'passed',
        durationMs: 50,
        detail: {
          chunks: [
            {
              rank: 1,
              ...makeBody('shared', 'Shared SOP'),
              denseScore: 0.77,
              bm25Score: 6.2,
              fusionScore: 0.0322,
              rerankScore: 0.95,
              docCodeMatch: true,
              inContext: true,
            },
          ],
          stageChunks: {
            shared: makeBody('shared', 'Shared SOP'),
            'd-only': makeBody('d-only', 'Dense Only SOP'),
            's-only': makeBody('s-only', 'Sparse Only SOP'),
          },
        },
      },
    ]);

    const denseDetail = trace.steps.find((s) => s.step === 'retrieve_dense')?.detail;
    const sparseDetail = trace.steps.find((s) => s.step === 'retrieve_sparse')?.detail;
    const rrfDetail = trace.steps.find((s) => s.step === 'retrieve_rrf')?.detail;

    const dense = resolveStageChunks('dense', trace, denseDetail);
    expect(dense.map((c) => [c.chunkId, c.denseScore, c.source])).toEqual([
      ['d-only', 0.91, 'orig'],
      ['shared', 0.77, 'both'],
    ]);

    const sparse = resolveStageChunks('bm25', trace, sparseDetail);
    expect(sparse.map((c) => [c.chunkId, c.bm25Score, c.source])).toEqual([
      ['s-only', 11.4, 'orig'],
      ['shared', 6.2, 'alt'],
    ]);

    const rrf = resolveStageChunks('rrf', trace, rrfDetail);
    expect(rrf.map((c) => [c.chunkId, c.fusionScore, c.denseScore, c.bm25Score, c.inPool])).toEqual([
      ['shared', 0.0322, 0.77, 6.2, true],
      ['d-only', 0.0163, 0.91, null, false],
      ['s-only', 0.0163, null, 11.4, false],
    ]);
  });
});
