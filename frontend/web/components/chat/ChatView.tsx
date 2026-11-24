'use client';

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Activity, ArrowUp, Sparkles, Square } from 'lucide-react';
import { Button, Skeleton } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import {
  BlurText,
  BorderBeam,
  InteractiveGrid,
  SpotlightCard,
} from '@/components/effects';
import { FadeIn } from '@/components/motion/Primitives';
import { getConversation } from '@/lib/api/endpoints';
import { applyEvent, endTurn, startTurn, type LiveTurn } from '@/lib/chat/live';
import { recallNearest, recallWarnings, rememberNearest, rememberWarnings } from '@/lib/chat/warning-store';
import { workspaceKey } from '@/lib/query/client';
import { useConversation, useMessageTrace } from '@/lib/query/hooks';
import { streamAnswer } from '@/lib/sse/stream';
import { useInspectorStore } from '@/store/inspector-store';
import { useSessionStore } from '@/store/session-store';
import { AnswerBlock } from './AnswerBlock';
import { PipelineInspectorPanel } from './inspector/PipelineInspectorPanel';

const STARTER_PROMPTS = [
  {
    title: 'Approval process',
    prompt: 'What approval steps and roles are required by our SOP?',
    tag: 'Procedure',
  },
  {
    title: 'Policy requirements',
    prompt: 'Tóm tắt các yêu cầu bắt buộc và thời hạn chính trong quy chế hiện hành.',
    tag: 'Tiếng Việt',
  },
  {
    title: 'Escalation & SLA',
    prompt: 'What is the escalation path and response SLA when an incident occurs?',
    tag: 'Operations',
  },
  {
    title: 'Compliance checklist',
    prompt: 'List the mandatory verification steps before completing this workflow.',
    tag: 'Checklist',
  },
] as const;

function UserBubble({ text }: { text: string }) {
  return (
    <FadeIn>
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-sm">
          {text}
        </p>
      </div>
    </FadeIn>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-border bg-muted/60 p-3.5 text-sm text-muted-foreground">
      {children}
    </p>
  );
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
  const workspace = useSessionStore((s) => s.workspace);
  const wid = workspace?.id ?? 'none';
  const history = useConversation(conversationId);
  const inspectorOpen = useInspectorStore((s) => s.open);
  const setInspectorOpen = useInspectorStore((s) => s.setOpen);
  const toggleInspector = useInspectorStore((s) => s.toggle);
  const [live, setLive] = useState<LiveTurn | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<string | 'live' | null>(null);
  // True from the end of the stream until the history reload settles: a new question must not
  // start in that window (it would race the reload and the URL change).
  const [finishing, setFinishing] = useState(false);
  const [draft, setDraft] = useState('');
  const [focused, setFocused] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
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
    // Auto-open the Pipeline Inspector in real time whenever the user sends a query.
    setInspectorOpen(true);
    setSelectedTurn('live');
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
      // Seed the trace cache before clearing `live` so the side-panel transitions without flicker.
      if (turn.messageId) {
        client.setQueryData(workspaceKey(wid, 'message-trace', cid, turn.messageId), {
          ...turn.trace,
          live: false,
        });
      }
      try {
        await client.fetchQuery({
          queryKey: workspaceKey(wid, 'conversation', cid),
          queryFn: () => getConversation(cid),
          staleTime: 0,
        });
        if (turn.messageId) setSelectedTurn(turn.messageId);
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
    if (inputRef.current) inputRef.current.style.height = 'auto';
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

  // Map each assistant message to its preceding user question for the Inspector header.
  const questionByAssistantId = new Map<string, string>();
  let lastUserQ: string | null = null;
  let lastAssistantId: string | null = null;
  for (const m of messages) {
    if (m.role === 'USER') {
      lastUserQ = m.content;
    } else {
      if (lastUserQ) questionByAssistantId.set(m.id, lastUserQ);
      lastAssistantId = m.id;
    }
  }

  const effectiveTarget: string | 'live' | null =
    selectedTurn === 'live'
      ? live
        ? 'live'
        : lastAssistantId
      : selectedTurn ?? (live ? 'live' : lastAssistantId);

  const inspectingLive = effectiveTarget === 'live' && live !== null;
  const activeConversationId = conversationId ?? live?.conversationId ?? createdId.current;
  const historicalMessageId =
    inspectorOpen && !inspectingLive && effectiveTarget && effectiveTarget !== 'live' ? effectiveTarget : null;
  const traceQuery = useMessageTrace(activeConversationId, historicalMessageId);

  const inspectedTrace = inspectingLive ? live.trace : (traceQuery.data ?? null);
  const inspectedQuestion = inspectingLive
    ? live.question
    : effectiveTarget && effectiveTarget !== 'live'
      ? (questionByAssistantId.get(effectiveTarget) ?? null)
      : null;

  function inspectTurn(target: string | 'live') {
    setSelectedTurn(target);
    setInspectorOpen(true);
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Slim Chat Toolbar */}
        <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b border-border/60 bg-background/70 px-4">
          <span className="truncate text-xs font-semibold text-muted-foreground">
            {history.data?.title ?? 'New conversation'}
          </span>
          <button
            type="button"
            onClick={toggleInspector}
            aria-expanded={inspectorOpen}
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-ring ${
              inspectorOpen
                ? 'border-primary/40 bg-primary-soft text-primary-strong'
                : 'border-border bg-card text-muted-foreground hover:border-border-strong hover:text-foreground'
            }`}
          >
            <Activity size={13} aria-hidden />
            <span>Pipeline Inspector</span>
            {streaming ? (
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary motion-safe:animate-pulse" />
            ) : null}
          </button>
        </div>

        <div className="chat-container relative flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {history.isLoading && conversationId ? <Skeleton count={3} height={80} /> : null}
            {history.isError ? <ErrorNote error={history.error} onRetry={() => void history.refetch()} /> : null}

            {empty ? (
              <div className="relative flex min-h-[60vh] flex-col items-center justify-center overflow-hidden rounded-3xl py-8">
                <InteractiveGrid
                  squareSize={42}
                  borderColor="rgba(148, 163, 184, 0.12)"
                  hoverFillColor="rgba(20, 184, 166, 0.12)"
                />
                <div className="relative z-10 w-full px-2 text-center">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary-soft px-3 py-1 text-xs font-semibold text-primary-strong">
                    <Sparkles size={13} aria-hidden />
                    {workspace?.name ?? 'SOPilot Workspace'}
                  </span>
                  <div className="mt-4 flex justify-center">
                    <BlurText
                      as="h1"
                      text="Ask a question about your SOPs"
                      className="justify-center text-2xl font-bold tracking-tight text-foreground sm:text-3xl"
                    />
                  </div>
                  <p className="mx-auto mt-2.5 max-w-lg text-sm text-muted-foreground">
                    Answers cite the documents you can read. Questions can be in English or Vietnamese.
                  </p>

                  <div className="mt-8 grid gap-3 text-left sm:grid-cols-2">
                    {STARTER_PROMPTS.map((item, idx) => (
                      <FadeIn key={item.title} delay={0.06 * idx}>
                        <SpotlightCard
                          onClick={() => {
                            setDraft(item.prompt);
                            inputRef.current?.focus();
                          }}
                          className="cursor-pointer p-4"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-foreground">{item.title}</span>
                            <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                              {item.tag}
                            </span>
                          </div>
                          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                            {item.prompt}
                          </p>
                        </SpotlightCard>
                      </FadeIn>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            {messages.map((m) => {
              if (m.role === 'USER') return <UserBubble key={m.id} text={m.content} />;
              if ('hidden' in m) {
                return (
                  <div key={m.id} className="space-y-1.5">
                    <HiddenNote reason={m.reason} />
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => inspectTurn(m.id)}
                        className="inline-flex cursor-pointer items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                      >
                        <Activity size={11} aria-hidden />
                        <span>Inspect pipeline</span>
                      </button>
                    </div>
                  </div>
                );
              }
              // A turn the client left mid-stream is stored with outcome ERROR (possibly with a partial text).
              if (m.outcome === 'ERROR') {
                return (
                  <div key={m.id} className="space-y-1.5">
                    <Note>
                      This answer could not be completed. Ask the question again to get a full answer.
                    </Note>
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => inspectTurn(m.id)}
                        className="inline-flex cursor-pointer items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                      >
                        <Activity size={11} aria-hidden />
                        <span>Inspect pipeline</span>
                      </button>
                    </div>
                  </div>
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
                  inspected={inspectorOpen && effectiveTarget === m.id}
                  onInspect={() => inspectTurn(m.id)}
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
                  reasoning={live.answer.reasoning}
                  reasoningMs={live.answer.reasoningMs}
                  messageId={live.phase === 'done' ? live.messageId : null}
                  inspected={inspectorOpen && inspectingLive}
                  onInspect={() => inspectTurn('live')}
                >
                  {live.phase === 'interrupted' ? (
                    <p role="alert" className="mt-3 text-sm text-warning-foreground">
                      The connection was interrupted, so this answer may be incomplete.{' '}
                      <button
                        type="button"
                        className="cursor-pointer font-semibold underline"
                        disabled={locked}
                        onClick={() => void send(live.question)}
                      >
                        Ask again
                      </button>
                    </p>
                  ) : null}
                  {live.phase === 'cancelled' ? <p className="mt-3 text-sm text-muted-foreground">Stopped.</p> : null}
                  {live.phase === 'error' ? (
                    <p role="alert" className="mt-3 text-sm text-danger-foreground">
                      {live.errorMessage}{' '}
                      <button
                        type="button"
                        className="cursor-pointer font-semibold underline"
                        disabled={locked}
                        onClick={() => void send(live.question)}
                      >
                        Try again
                      </button>
                    </p>
                  ) : null}
                </AnswerBlock>
              </>
            ) : null}

            <div ref={bottom} />
          </div>
        </div>

        {/* Floating Command Composer */}
        <div className="border-t border-border/60 bg-background/85 px-4 py-3.5 backdrop-blur-md">
          <form
            onSubmit={submit}
            className="relative mx-auto max-w-3xl overflow-hidden rounded-2xl border border-border bg-card shadow-[var(--shadow-md)] transition-colors focus-within:border-primary/50"
          >
            <BorderBeam active={streaming || focused} durationSec={streaming ? 4 : 8} rx={16} />
            <div className="relative z-10 flex items-end gap-2 p-2.5 pl-4">
              <textarea
                ref={inputRef}
                aria-label="Question"
                rows={1}
                value={draft}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                onChange={(e) => {
                  setDraft(e.target.value);
                  e.currentTarget.style.height = 'auto';
                  e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 160)}px`;
                }}
                onKeyDown={onKeyDown}
                placeholder="Ask about your SOPs (EN / VI)…"
                className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-1.5 text-sm leading-5 text-foreground placeholder:text-placeholder focus:outline-none"
              />
              {streaming ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  icon={<Square size={12} aria-hidden className="fill-current" />}
                  onClick={() => abort.current?.abort()}
                >
                  Stop
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="sm"
                  aria-label="Send"
                  icon={<ArrowUp size={15} aria-hidden />}
                  disabled={locked || draft.trim().length === 0}
                >
                  Send
                </Button>
              )}
            </div>
            <div className="relative z-10 flex items-center justify-between border-t border-border/50 bg-muted/35 px-4 py-1.5 text-[11px] text-muted-foreground">
              <span>Grounded only in documents you can access</span>
              <span className="hidden sm:inline">
                <kbd className="rounded border border-border bg-card px-1 font-mono text-[10px]">Enter</kbd> send ·{' '}
                <kbd className="rounded border border-border bg-card px-1 font-mono text-[10px]">Shift+Enter</kbd> newline
              </span>
            </div>
          </form>
        </div>
      </div>

      <PipelineInspectorPanel
        open={inspectorOpen}
        onToggle={toggleInspector}
        trace={inspectedTrace}
        question={inspectedQuestion}
        loading={!inspectingLive && traceQuery.isLoading}
        error={!inspectingLive && traceQuery.isError}
        onRetry={() => void traceQuery.refetch()}
        isLive={Boolean(inspectingLive && streaming)}
      />
    </div>
  );
}
