import { describe, expect, it } from 'vitest';
import { applyEvent, endTurn, startTurn } from './live';
import { thoughtLabel } from './labels';

describe('live turn', () => {
  it('streams deltas, then replace overrides the text and done.finalText is authoritative', () => {
    let t = startTurn('q');
    t = applyEvent(t, { type: 'meta', conversationId: 'c1', messageId: 'm1', mode: 'answer', lang: 'en' });
    t = applyEvent(t, { type: 'delta', text: 'Hel' });
    t = applyEvent(t, { type: 'delta', text: 'lo' });
    expect(t.answer.text).toBe('Hello');
    t = applyEvent(t, { type: 'replace', text: 'Fixed', reason: 'citation' });
    expect(t.answer.text).toBe('Fixed');
    t = applyEvent(t, {
      type: 'done',
      finalText: 'Final',
      outcome: 'ANSWERED',
      refusalReason: null,
      warnings: [{ code: 'NUMBER_NOT_IN_SOURCES', values: ['5'] }],
      usage: null,
    });
    t = endTurn(t, { status: 'done' });
    expect(t).toMatchObject({ phase: 'done', conversationId: 'c1', messageId: 'm1' });
    expect(t.answer.text).toBe('Final');
    expect(t.warnings).toHaveLength(1);
  });

  it('keeps the nearest documents of a NO_EVIDENCE refusal', () => {
    let t = startTurn('q');
    t = applyEvent(t, {
      type: 'refusal',
      text: 'Nothing found',
      reason: 'NO_EVIDENCE',
      nearestDocuments: [{ documentId: 'd1', title: 'SOP-Safety' }],
    });
    t = applyEvent(t, {
      type: 'done',
      finalText: 'Nothing found',
      outcome: 'REFUSED',
      refusalReason: 'NO_EVIDENCE',
      warnings: [],
      usage: null,
    });
    expect(t.refusal?.reason).toBe('NO_EVIDENCE');
    expect(t.refusal?.nearest).toEqual([{ documentId: 'd1', title: 'SOP-Safety' }]);
  });

  it('keeps a partial answer when the stream ends early and marks how it ended', () => {
    let t = startTurn('q');
    t = applyEvent(t, { type: 'delta', text: 'Partial' });
    expect(endTurn(t, { status: 'interrupted' })).toMatchObject({ phase: 'interrupted', answer: { text: 'Partial' } });
    expect(endTurn(t, { status: 'cancelled' }).phase).toBe('cancelled');
    expect(endTurn(t, { status: 'error', code: 'LLM_UNAVAILABLE', message: 'Try later.', traceId: null })).toMatchObject({
      phase: 'error',
      errorMessage: 'Try later.',
    });
  });

  it('keeps reasoning out of the answer text and records how long it took', () => {
    let t = startTurn('q');
    t = applyEvent(t, { type: 'reasoning', text: 'Look at ' });
    t = applyEvent(t, { type: 'reasoning', text: 'the table.' });
    expect(t.answer).toMatchObject({ reasoning: 'Look at the table.', reasoningMs: null, text: '' });
    t = applyEvent(t, { type: 'reasoning_done', durationMs: 9400 });
    t = applyEvent(t, { type: 'delta', text: 'Answer' });
    expect(t.answer).toMatchObject({ reasoning: 'Look at the table.', reasoningMs: 9400, text: 'Answer' });
  });
});

describe('thoughtLabel', () => {
  it('is live while thinking, then rounds to seconds (at least 1)', () => {
    expect(thoughtLabel(null, true)).toBe('Thinking…');
    expect(thoughtLabel(9400, false)).toBe('Thought for 9 s');
    expect(thoughtLabel(120, false)).toBe('Thought for 1 s');
    expect(thoughtLabel(null, false)).toBe('Reasoning');
  });
});
