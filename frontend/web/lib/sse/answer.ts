// Folds stream events into the text a chat bubble shows (R4): `replace` and `refusal` override the
// streamed text, `done.finalText` is authoritative. Reasoning is kept apart from the answer: it
// only feeds the collapsible "Thought for N s" block and never becomes answer text.

import type { Citation, StreamEvent } from '@/lib/api/types';

export interface AnswerState {
  text: string;
  refused: boolean;
  citations: Citation[];
  finished: boolean;
  /** Reasoning text so far; empty when the model did not think (or it was withheld). */
  reasoning: string;
  /** Set by `reasoning_done`; null while the model is still thinking or never did. */
  reasoningMs: number | null;
}

export const emptyAnswer: AnswerState = {
  text: '',
  refused: false,
  citations: [],
  finished: false,
  reasoning: '',
  reasoningMs: null,
};

export function reduceAnswer(state: AnswerState, event: StreamEvent): AnswerState {
  switch (event.type) {
    case 'reasoning':
      return { ...state, reasoning: state.reasoning + event.text };
    case 'reasoning_done':
      return { ...state, reasoningMs: event.durationMs };
    case 'delta':
      return { ...state, text: state.text + event.text };
    case 'replace':
      return { ...state, text: event.text };
    case 'refusal':
      return { ...state, text: event.text, refused: true };
    case 'citations':
      return { ...state, citations: event.citations };
    case 'done':
      return { ...state, text: event.finalText, finished: true };
    default:
      return state;
  }
}
