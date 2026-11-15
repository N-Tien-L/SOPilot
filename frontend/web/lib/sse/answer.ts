// Folds stream events into the text a chat bubble shows (R4): `replace` and `refusal` override the
// streamed text, `done.finalText` is authoritative.

import type { Citation, StreamEvent } from '@/lib/api/types';

export interface AnswerState {
  text: string;
  refused: boolean;
  citations: Citation[];
  finished: boolean;
}

export const emptyAnswer: AnswerState = { text: '', refused: false, citations: [], finished: false };

export function reduceAnswer(state: AnswerState, event: StreamEvent): AnswerState {
  switch (event.type) {
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
