// The turn being streamed right now (R4): question, partial answer, and how it ended. Pure state
// so the end states can be tested without a browser.

import type { AnswerWarning, PipelineTrace, StreamEvent } from '@/lib/api/types';
import { emptyAnswer, reduceAnswer, type AnswerState } from '@/lib/sse/answer';
import type { StreamEnd } from '@/lib/sse/stream';
import { createInitialTrace, finalizeAbortedTrace, reducePipelineTrace } from './pipeline-trace';

export type LivePhase = 'streaming' | 'done' | 'error' | 'cancelled' | 'interrupted';

export interface LiveTurn {
  question: string;
  answer: AnswerState;
  trace: PipelineTrace;
  conversationId: string | null;
  messageId: string | null;
  refusal: { reason: string; nearest: { documentId: string; title: string }[] } | null;
  warnings: AnswerWarning[];
  phase: LivePhase;
  errorMessage: string | null;
}

export function startTurn(question: string): LiveTurn {
  return {
    question,
    answer: emptyAnswer,
    trace: createInitialTrace(question),
    conversationId: null,
    messageId: null,
    refusal: null,
    warnings: [],
    phase: 'streaming',
    errorMessage: null,
  };
}

export function applyEvent(turn: LiveTurn, event: StreamEvent): LiveTurn {
  const answer = reduceAnswer(turn.answer, event);
  const trace = reducePipelineTrace(turn.trace, event);
  switch (event.type) {
    case 'meta':
      return { ...turn, answer, trace, conversationId: event.conversationId, messageId: event.messageId };
    case 'refusal':
      return { ...turn, answer, trace, refusal: { reason: event.reason, nearest: event.nearestDocuments } };
    case 'done':
      return {
        ...turn,
        answer,
        trace,
        warnings: event.warnings,
        refusal: turn.refusal ?? (event.refusalReason ? { reason: event.refusalReason, nearest: [] } : null),
      };
    default:
      return { ...turn, answer, trace };
  }
}

/** Folds the stream's terminal state in. A partial answer is kept and marked, never dropped. */
export function endTurn(turn: LiveTurn, end: StreamEnd): LiveTurn {
  const trace = finalizeAbortedTrace(turn.trace, end);
  switch (end.status) {
    case 'done':
      return { ...turn, trace, phase: 'done' };
    case 'error':
      return { ...turn, trace, phase: 'error', errorMessage: end.message };
    case 'cancelled':
      return { ...turn, trace, phase: 'cancelled' };
    default:
      return { ...turn, trace, phase: 'interrupted' };
  }
}
