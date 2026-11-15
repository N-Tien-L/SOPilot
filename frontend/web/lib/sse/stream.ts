// POST /ai/v1/conversations/{id|new}/messages as a fetch stream (C3, R4).
// Every call ends in exactly one defined state; nothing is left hanging.

import { AI_BASE, authorizedFetch } from '@/lib/api/http';
import { ApiError, NETWORK_ERROR_MESSAGE, parseAiError } from '@/lib/api/errors';
import type { StreamEvent } from '@/lib/api/types';
import { createSseParser, decodeStreamEvent } from './parser';
import { trackStream } from './registry';

export type StreamEnd =
  | { status: 'done' } //          `done` event received
  | { status: 'error'; code: string; message: string; traceId: string | null } // `error` event or HTTP error
  | { status: 'cancelled' } //     the caller (or a workspace switch) aborted
  | { status: 'interrupted' }; //  the connection ended or broke before `done`/`error`

export interface StreamAnswerOptions {
  /** A conversation id, or `new` to start one. */
  conversationId: string;
  content: string;
  lang?: 'vi' | 'en';
  signal?: AbortSignal;
  onEvent: (event: StreamEvent) => void;
}

export async function streamAnswer(options: StreamAnswerOptions): Promise<StreamEnd> {
  const controller = new AbortController();
  const untrack = trackStream(controller);
  const onCallerAbort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener('abort', onCallerAbort);

  try {
    let response: Response;
    try {
      response = await authorizedFetch(
        AI_BASE,
        `/conversations/${encodeURIComponent(options.conversationId)}/messages`,
        {
          method: 'POST',
          body: { content: options.content, ...(options.lang ? { lang: options.lang } : {}) },
          headers: { Accept: 'text/event-stream' },
          signal: controller.signal,
        },
      );
    } catch (error) {
      if (controller.signal.aborted) return { status: 'cancelled' };
      const message = error instanceof ApiError ? error.message : NETWORK_ERROR_MESSAGE;
      return { status: 'error', code: 'NETWORK_ERROR', message, traceId: null };
    }

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = undefined;
      }
      const error = parseAiError(response.status, body);
      return { status: 'error', code: `HTTP_${response.status}`, message: error.message, traceId: null };
    }
    if (!response.body) return { status: 'interrupted' };

    let terminal: StreamEnd | null = null;
    const parser = createSseParser((raw) => {
      const event = decodeStreamEvent(raw);
      if (!event) return;
      options.onEvent(event);
      if (event.type === 'done') terminal = { status: 'done' };
      else if (event.type === 'error') {
        terminal = { status: 'error', code: event.code, message: event.message, traceId: null };
      }
    });

    const reader = response.body.getReader();
    const cancelReader = () => {
      reader.cancel().catch(() => undefined);
    };
    if (controller.signal.aborted) cancelReader();
    else controller.signal.addEventListener('abort', cancelReader, { once: true });
    const decoder = new TextDecoder();
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parser.push(decoder.decode(value, { stream: true }));
      }
      parser.push(decoder.decode());
    } catch {
      if (controller.signal.aborted) return { status: 'cancelled' };
      return terminal ?? { status: 'interrupted' };
    } finally {
      controller.signal.removeEventListener('abort', cancelReader);
      parser.end();
    }
    if (terminal) return terminal;
    return controller.signal.aborted ? { status: 'cancelled' } : { status: 'interrupted' };
  } finally {
    options.signal?.removeEventListener('abort', onCallerAbort);
    untrack();
  }
}
