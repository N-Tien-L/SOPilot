'use client';

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Send, Square } from 'lucide-react';
import { Button, Skeleton } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import { getConversation } from '@/lib/api/endpoints';
import { applyEvent, endTurn, startTurn, type LiveTurn } from '@/lib/chat/live';
import { recallNearest, recallWarnings, rememberNearest, rememberWarnings } from '@/lib/chat/warning-store';
import { workspaceKey } from '@/lib/query/client';
import { useConversation } from '@/lib/query/hooks';
import { streamAnswer } from '@/lib/sse/stream';
import { useSessionStore } from '@/store/session-store';
import { AnswerBlock } from './AnswerBlock';

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] whitespace-pre-wrap rounded-lg rounded-br-sm bg-primary px-4 py-2 text-primary-foreground">{text}</p>
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-dashed border-border bg-muted p-3 text-sm text-muted-foreground">{children}</p>;
}

function HiddenNote({ reason }: { reason: string }) {
  return (
    <Note>
      {reason === 'DOCUMENT_DELETED'
        ? 'This answer is no longer available because a document it used was deleted.'
        : 'This answer is no longer available because you no longer have access to a document it used.'}
    </Note>
  );
}

export function ChatView({ conversationId }: { conversationId: string | null }) {
  const router = useRouter();
  const client = useQueryClient();
  const wid = useSessionStore((s) => s.workspace?.id ?? 'none');
  const history = useConversation(conversationId);
  const [live, setLive] = useState<LiveTurn | null>(null);
  // True from the end of the stream until the history reload settles: a new question must not
  // start in that window (it would race the reload and the URL change).
  const [finishing, setFinishing] = useState(false);
  const [draft, setDraft] = useState('');
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  // The conversation the server created for this view, so a retry continues it instead of
  // starting a second one.
  const createdId = useRef<string | null>(null);

  const streaming = live?.phase === 'streaming';
  const locked = streaming || finishing;

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      abort.current?.abort();
    };
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' });
  }, [live?.answer.text, history.data?.messages.length, live?.phase]);

  async function send(question: string) {
    const controller = new AbortController();
    abort.current = controller;
    let turn = startTurn(question);
    setLive(turn);
    const end = await streamAnswer({
      conversationId: conversationId ?? createdId.current ?? 'new',
      content: question,
      signal: controller.signal,
      onEvent: (event) => {
        turn = applyEvent(turn, event);
        setLive(turn);
      },
    });
    abort.current = null;
    turn = endTurn(turn, end);
    setLive(turn);
    if (turn.conversationId) createdId.current = turn.conversationId;
    // The id from `meta` exists only once the turn is stored; if it is unknown to the server, start fresh.
    if (end.status === 'error' && end.code === 'HTTP_404' && !conversationId) createdId.current = null;
    void client.invalidateQueries({ queryKey: workspaceKey(wid, 'conversations') });
    const cid = turn.conversationId ?? conversationId;
    if (end.status === 'done' && cid) {
      setFinishing(true);
      // Warnings and the closest documents exist only in the stream; keep them for the history view.
      rememberWarnings(turn.messageId, turn.warnings);
      rememberNearest(turn.messageId, turn.refusal?.nearest ?? []);
      try {
        await client.fetchQuery({
          queryKey: workspaceKey(wid, 'conversation', cid),
          queryFn: () => getConversation(cid),
          staleTime: 0,
        });
        setLive(null);
        if (!conversationId && mounted.current) router.replace(`/chat/${cid}`);
      } catch {
        // Keep the streamed answer on screen; the history reloads on the next visit.
      } finally {
        setFinishing(false);
      }
    }
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const question = draft.trim();
    if (!question || locked) return;
    setDraft('');
    void send(question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  const messages = history.data?.messages ?? [];
  const empty = messages.length === 0 && !live && !history.isLoading;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {history.isLoading && conversationId ? <Skeleton count={3} height={72} /> : null}
        {history.isError ? <ErrorNote error={history.error} /> : null}
        {empty ? (
          <div className="mt-16 text-center">
            <h1 className="text-2xl font-semibold">Ask a question about your SOPs</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Answers cite the documents you can read. Questions can be in English or Vietnamese.
            </p>
          </div>
        ) : null}
        {messages.map((m) => {
          if (m.role === 'USER') return <UserBubble key={m.id} text={m.content} />;
          if ('hidden' in m) return <HiddenNote key={m.id} reason={m.reason} />;
          // A turn the client left mid-stream is stored with outcome ERROR (possibly with a partial text).
          if (m.outcome === 'ERROR') {
            return (
              <Note key={m.id}>
                This answer could not be completed. Ask the question again to get a full answer.
              </Note>
            );
          }
          return (
            <AnswerBlock
              key={m.id}
              text={m.content}
              citations={m.citations}
              refusal={m.refusalReason ? { reason: m.refusalReason, nearest: recallNearest(m.id) } : null}
              warnings={recallWarnings(m.id)}
              streaming={false}
              messageId={m.id}
            />
          );
        })}
        {live ? (
          <>
            <UserBubble text={live.question} />
            <AnswerBlock
              text={live.answer.text}
              citations={live.answer.citations}
              refusal={live.refusal}
              warnings={live.warnings}
              streaming={live.phase === 'streaming'}
              messageId={live.phase === 'done' ? live.messageId : null}
            >
              {live.phase === 'interrupted' ? (
                <p role="alert" className="mt-3 text-sm text-warning-foreground">
                  The connection was interrupted, so this answer may be incomplete.{' '}
                  <button type="button" className="underline" disabled={locked} onClick={() => void send(live.question)}>
                    Ask again
                  </button>
                </p>
              ) : null}
              {live.phase === 'cancelled' ? <p className="mt-3 text-sm text-muted-foreground">Stopped.</p> : null}
              {live.phase === 'error' ? (
                <p role="alert" className="mt-3 text-sm text-danger-foreground">
                  {live.errorMessage}{' '}
                  <button type="button" className="underline" disabled={locked} onClick={() => void send(live.question)}>
                    Try again
                  </button>
                </p>
              ) : null}
            </AnswerBlock>
          </>
        ) : null}
        <div ref={bottom} />
      </div>
      <form onSubmit={submit} className="flex items-end gap-2 border-t border-border bg-background p-4">
        <textarea
          aria-label="Question"
          rows={1}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question about your SOPs…"
          className="max-h-40 min-h-10 flex-1 resize-y rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
        />
        {streaming ? (
          <Button type="button" variant="outline" icon={<Square size={14} aria-hidden />} onClick={() => abort.current?.abort()}>
            Stop
          </Button>
        ) : (
          <Button type="submit" icon={<Send size={14} aria-hidden />} disabled={locked || draft.trim().length === 0}>
            Send
          </Button>
        )}
      </form>
    </div>
  );
}
