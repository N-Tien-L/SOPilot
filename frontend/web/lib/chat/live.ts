// The turn being streamed right now (R4): question, partial answer, and how it ended. Pure state
// so the end states can be tested without a browser.

import type { AnswerWarning, StreamEvent } from '@/lib/api/types';
import { emptyAnswer, reduceAnswer, type AnswerState } from '@/lib/sse/answer';
import type { StreamEnd } from '@/lib/sse/stream';

export type LivePhase = 'streaming' | 'done' | 'error' | 'cancelled' | 'interrupted';

export interface LiveTurn {
  question: string;
  answer: AnswerState;
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
  switch (event.type) {
    case 'meta':
      return { ...turn, answer, conversationId: event.conversationId, messageId: event.messageId };
    case 'refusal':
      return { ...turn, answer, refusal: { reason: event.reason, nearest: event.nearestDocuments } };
    case 'done':
      return {
        ...turn,
        answer,
        warnings: event.warnings,
        refusal: turn.refusal ?? (event.refusalReason ? { reason: event.refusalReason, nearest: [] } : null),
      };
    default:
      return { ...turn, answer };
  }
}

/** Folds the stream's terminal state in. A partial answer is kept and marked, never dropped. */
export function endTurn(turn: LiveTurn, end: StreamEnd): LiveTurn {
  switch (end.status) {
    case 'done':
      return { ...turn, phase: 'done' };
    case 'error':
      return { ...turn, phase: 'error', errorMessage: end.message };
    case 'cancelled':
      return { ...turn, phase: 'cancelled' };
    default:
      return { ...turn, phase: 'interrupted' };
  }
}
