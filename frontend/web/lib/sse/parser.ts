// Incremental Server-Sent Events parser (frontend-nfrs C3). EventSource cannot send a body or a
// header, so the stream is read with fetch and decoded here.

import type { AnswerWarning, Citation, RefusalReason, StreamEvent } from '@/lib/api/types';

export interface RawSseEvent {
  event: string;
  data: string;
}

export function createSseParser(onEvent: (event: RawSseEvent) => void) {
  let buffer = '';
  let eventName = '';
  let dataLines: string[] = [];
  let sawCr = false;

  function dispatch(): void {
    if (dataLines.length > 0) onEvent({ event: eventName || 'message', data: dataLines.join('\n') });
    eventName = '';
    dataLines = [];
  }

  function handleLine(line: string): void {
    if (line === '') return dispatch();
    if (line.startsWith(':')) return; // comment, e.g. the ": ping" keep-alive
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') eventName = value;
    else if (field === 'data') dataLines.push(value);
    // id and retry are not used by the answer stream.
  }

  return {
    push(chunk: string): void {
      let text = chunk;
      if (sawCr && text.startsWith('\n')) text = text.slice(1); // CRLF split across chunks
      sawCr = false;
      buffer += text;
      let start = 0;
      for (let i = 0; i < buffer.length; i++) {
        const ch = buffer[i];
        if (ch !== '\n' && ch !== '\r') continue;
        handleLine(buffer.slice(start, i));
        if (ch === '\r') {
          if (buffer[i + 1] === '\n') i++;
          else if (i + 1 === buffer.length) sawCr = true;
        }
        start = i + 1;
      }
      buffer = buffer.slice(start);
    },
    /** End of stream: an unterminated event is dropped, as the SSE spec requires. */
    end(): void {
      buffer = '';
      eventName = '';
      dataLines = [];
    },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

/** Maps a raw event to a typed one; unknown events and malformed JSON return null. */
export function decodeStreamEvent(raw: RawSseEvent): StreamEvent | null {
  let data: unknown;
  try {
    data = JSON.parse(raw.data);
  } catch {
    return null;
  }
  switch (raw.event) {
    case 'meta':
      if (!isRecord(data)) return null;
      return {
        type: 'meta',
        conversationId: str(data.conversationId),
        messageId: str(data.messageId),
        mode: str(data.mode),
        lang: str(data.lang),
      };
    case 'reasoning':
      return isRecord(data) ? { type: 'reasoning', text: str(data.text) } : null;
    case 'reasoning_done':
      return isRecord(data) && typeof data.durationMs === 'number'
        ? { type: 'reasoning_done', durationMs: data.durationMs }
        : null;
    case 'delta':
      return isRecord(data) ? { type: 'delta', text: str(data.text) } : null;
    case 'replace':
      return isRecord(data) ? { type: 'replace', text: str(data.text), reason: str(data.reason) } : null;
    case 'refusal':
      if (!isRecord(data)) return null;
      return {
        type: 'refusal',
        text: str(data.text),
        reason: str(data.reason) as RefusalReason,
        nearestDocuments: Array.isArray(data.nearestDocuments)
          ? (data.nearestDocuments as { documentId: string; title: string }[])
          : [],
      };
    case 'citations':
      return Array.isArray(data) ? { type: 'citations', citations: data as Citation[] } : null;
    case 'done':
      if (!isRecord(data)) return null;
      return {
        type: 'done',
        finalText: str(data.finalText),
        outcome: str(data.outcome),
        refusalReason: typeof data.refusalReason === 'string' ? data.refusalReason : null,
        warnings: Array.isArray(data.warnings) ? (data.warnings as AnswerWarning[]) : [],
        usage: isRecord(data.usage) ? (data.usage as { questionsLeftToday: number }) : null,
      };
    case 'error':
      return isRecord(data) ? { type: 'error', code: str(data.code), message: str(data.message) } : null;
    default:
      return null;
  }
}
