import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StreamEvent } from '@/lib/api/types';
import { emptyAnswer, reduceAnswer } from './answer';
import { createSseParser, decodeStreamEvent, type RawSseEvent } from './parser';
import { openStreamCount } from './registry';
import { streamAnswer } from './stream';

function parseAll(chunks: string[]): RawSseEvent[] {
  const out: RawSseEvent[] = [];
  const parser = createSseParser((e) => out.push(e));
  chunks.forEach((c) => parser.push(c));
  parser.end();
  return out;
}

describe('SSE parser', () => {
  it('parses events split at arbitrary chunk boundaries', () => {
    const wire = 'event: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"text":"lo"}\n\n';
    for (let cut = 1; cut < wire.length; cut += 7) {
      const events = parseAll([wire.slice(0, cut), wire.slice(cut)]);
      expect(events.map((e) => e.data)).toEqual(['{"text":"Hel"}', '{"text":"lo"}']);
    }
  });

  it('handles CRLF (also split between chunks), comments and multi-line data', () => {
    const events = parseAll([': ping\r', '\nevent: delta\r\ndata: a\r\ndata: b\r\n\r\n']);
    expect(events).toEqual([{ event: 'delta', data: 'a\nb' }]);
  });

  it('drops an unterminated trailing event', () => {
    expect(parseAll(['event: delta\ndata: {"text":"x"}\n'])).toEqual([]);
  });

  it('keeps multibyte text intact', () => {
    const events = parseAll(['event: delta\ndata: {"text":"Quy trình 🚀"}\n\n']);
    expect(decodeStreamEvent(events[0])).toEqual({ type: 'delta', text: 'Quy trình 🚀' });
  });
});

describe('decodeStreamEvent', () => {
  it('decodes every event type', () => {
    const cases: [string, unknown, StreamEvent['type']][] = [
      ['meta', { conversationId: 'c', messageId: 'm', mode: 'rag', lang: 'en' }, 'meta'],
      ['reasoning', { text: 'check the table' }, 'reasoning'],
      ['reasoning_done', { durationMs: 9000 }, 'reasoning_done'],
      ['delta', { text: 'x' }, 'delta'],
      ['replace', { text: 'y', reason: 'GUARD' }, 'replace'],
      ['refusal', { text: 'no', reason: 'NO_EVIDENCE', nearestDocuments: [] }, 'refusal'],
      ['citations', [{ n: 1, documentId: 'd', versionId: 'v', title: 't', page: 1, charStart: 0, charEnd: 5, snippet: 's' }], 'citations'],
      ['done', { finalText: 'f', outcome: 'ANSWERED', refusalReason: null, warnings: [], usage: null }, 'done'],
      ['error', { code: 'LLM_UNAVAILABLE', message: 'Try later.' }, 'error'],
    ];
    for (const [event, data, type] of cases) {
      expect(decodeStreamEvent({ event, data: JSON.stringify(data) })?.type).toBe(type);
    }
  });

  it('returns null for unknown events and malformed JSON', () => {
    expect(decodeStreamEvent({ event: 'weird', data: '{}' })).toBeNull();
    expect(decodeStreamEvent({ event: 'delta', data: '{not json' })).toBeNull();
    expect(decodeStreamEvent({ event: 'reasoning_done', data: '{}' })).toBeNull();
  });
});

describe('reduceAnswer (R4)', () => {
  const apply = (events: StreamEvent[]) => events.reduce(reduceAnswer, emptyAnswer);

  it('accumulates deltas and takes finalText on done', () => {
    const state = apply([
      { type: 'delta', text: 'See [1] and [9]' },
      { type: 'done', finalText: 'See [1]', outcome: 'ANSWERED', refusalReason: null, warnings: [], usage: null },
    ]);
    expect(state).toMatchObject({ text: 'See [1]', finished: true });
  });

  it('replace overrides streamed text; refusal overrides and flags', () => {
    expect(apply([{ type: 'delta', text: 'leak' }, { type: 'replace', text: 'Blocked.', reason: 'GUARD' }]).text).toBe('Blocked.');
    const refused = apply([{ type: 'refusal', text: 'No evidence.', reason: 'NO_EVIDENCE', nearestDocuments: [] }]);
    expect(refused).toMatchObject({ text: 'No evidence.', refused: true });
  });
});

function sseResponse(chunks: string[], opts: { hang?: boolean; fail?: boolean } = {}): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      if (opts.fail) controller.error(new Error('connection reset'));
      else if (!opts.hang) controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const doneFrame = frame('done', { finalText: 'ok', outcome: 'ANSWERED', refusalReason: null, warnings: [], usage: null });

describe('streamAnswer end states (R4)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('ends "done" after a full answer and reports events in order', async () => {
    const fetchMock = vi.fn(async () => sseResponse([frame('meta', { conversationId: 'c', messageId: 'm', mode: 'x', lang: 'en' }), frame('delta', { text: 'Hi' }), doneFrame]));
    vi.stubGlobal('fetch', fetchMock);
    const seen: string[] = [];
    const end = await streamAnswer({ conversationId: 'new', content: 'q', onEvent: (e) => seen.push(e.type) });
    expect(end).toEqual({ status: 'done' });
    expect(seen).toEqual(['meta', 'delta', 'done']);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/ai/v1/conversations/new/messages');
    expect(init.method).toBe('POST');
    expect(openStreamCount()).toBe(0);
  });

  it('ends "error" with the code and fixed message of an error event', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse([frame('error', { code: 'LLM_UNAVAILABLE', message: 'Try later.' })])));
    const end = await streamAnswer({ conversationId: 'c1', content: 'q', onEvent: () => {} });
    expect(end).toMatchObject({ status: 'error', code: 'LLM_UNAVAILABLE', message: 'Try later.' });
  });

  it('ends "error" with the fixed detail when the HTTP status is not 2xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'question answering is not available' }), { status: 503 })));
    const end = await streamAnswer({ conversationId: 'new', content: 'q', onEvent: () => {} });
    expect(end).toMatchObject({ status: 'error', code: 'HTTP_503', message: 'question answering is not available' });
  });

  it('ends "interrupted" when the stream closes or breaks before done', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse([frame('delta', { text: 'par' })])));
    expect(await streamAnswer({ conversationId: 'new', content: 'q', onEvent: () => {} })).toEqual({ status: 'interrupted' });
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse([frame('delta', { text: 'par' })], { fail: true })));
    expect(await streamAnswer({ conversationId: 'new', content: 'q', onEvent: () => {} })).toEqual({ status: 'interrupted' });
    expect(openStreamCount()).toBe(0);
  });

  it('ends "cancelled" when the caller aborts mid-stream', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      const response = sseResponse([frame('delta', { text: 'a' })], { hang: true });
      init.signal?.addEventListener('abort', () => undefined);
      return response;
    }));
    const controller = new AbortController();
    const seen: string[] = [];
    const pending = streamAnswer({
      conversationId: 'new',
      content: 'q',
      signal: controller.signal,
      onEvent: (e) => {
        seen.push(e.type);
        controller.abort();
      },
    });
    expect(await pending).toEqual({ status: 'cancelled' });
    expect(seen).toEqual(['delta']);
    expect(openStreamCount()).toBe(0);
  });

  it('ends "cancelled" when aborted before the request starts', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      return sseResponse([doneFrame]);
    }));
    const controller = new AbortController();
    controller.abort();
    expect(await streamAnswer({ conversationId: 'new', content: 'q', signal: controller.signal, onEvent: () => {} })).toEqual({ status: 'cancelled' });
  });

  it('ends "error" with a fixed message when the network is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const end = await streamAnswer({ conversationId: 'new', content: 'q', onEvent: () => {} });
    expect(end).toMatchObject({ status: 'error', code: 'NETWORK_ERROR' });
  });
});
