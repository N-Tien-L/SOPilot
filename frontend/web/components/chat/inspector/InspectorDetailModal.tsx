'use client';

import { useMemo, useState } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { Check, Copy } from 'lucide-react';
import { Badge, Button, Modal } from '@/components/ui';
import { SafeMarkdown } from '@/components/viewer/SafeMarkdown';
import type { PipelineTrace, PromptMessageTrace, RetrievedChunkTrace } from '@/lib/api/types';
import { cn } from '@/lib/utils';

export type ChunkStageKind = 'chunks-dense' | 'chunks-bm25' | 'chunks-rrf' | 'chunks-rerank';

export type InspectorModalTarget =
  | {
      kind: ChunkStageKind;
      chunks: RetrievedChunkTrace[];
    }
  | {
      kind: 'prompt';
      messages: PromptMessageTrace[];
      promptVersion?: string;
      model?: string | null;
      promptTokens?: number | null;
    }
  | { kind: 'raw'; trace: PipelineTrace };

const CHUNK_DIALOG: Record<
  ChunkStageKind,
  {
    title: string;
    description: string;
    metric: 'rerankScore' | 'denseScore' | 'bm25Score' | 'fusionScore';
    digits: number;
  }
> = {
  'chunks-rerank': {
    title: 'Reranked passages',
    description: 'Cross-encoder score, highest first. Passages in context went to the answer model.',
    metric: 'rerankScore',
    digits: 3,
  },
  'chunks-dense': {
    title: 'Meaning search results',
    description: 'Cosine similarity of the question and passage embeddings, highest first.',
    metric: 'denseScore',
    digits: 4,
  },
  'chunks-bm25': {
    title: 'Keyword search results',
    description: 'BM25 keyword score, highest first.',
    metric: 'bm25Score',
    digits: 2,
  },
  'chunks-rrf': {
    title: 'Merged results',
    description: 'Reciprocal rank fusion of both searches, before the reranker.',
    metric: 'fusionScore',
    digits: 4,
  },
};

function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard unavailable in insecure contexts.
    }
  }

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      icon={copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
      onClick={() => void onCopy()}
    >
      {copied ? 'Copied' : label}
    </Button>
  );
}

function ChunkExplorer({
  chunks,
  stageKind,
}: {
  chunks: RetrievedChunkTrace[];
  stageKind: ChunkStageKind;
}) {
  const { metric, digits } = CHUNK_DIALOG[stageKind];
  const reduced = useReducedMotion() ?? false;

  const sorted = useMemo(() => {
    const withScore = chunks.filter((c) => c[metric] !== null);
    const pool = withScore.length > 0 ? withScore : chunks;
    return [...pool].sort((a, b) => (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity));
  }, [chunks, metric]);

  const [selected, setSelected] = useState<string>(sorted[0]?.chunkId ?? '');
  const [textMode, setTextMode] = useState<'formatted' | 'raw'>('formatted');

  const max = Math.max(...sorted.map((c) => c[metric] ?? 0), 0.0001);
  const active = sorted.find((c) => c.chunkId === selected) ?? sorted[0];

  if (!active) {
    return <p className="py-6 text-sm text-muted-foreground">No passages were retrieved for this stage.</p>;
  }

  return (
    <div className="space-y-4">
      <ul aria-label="Passages" className="max-h-64 overflow-y-auto rounded-xl border border-border bg-card">
        {sorted.map((c, i) => {
          const score = c[metric];
          const on = c.chunkId === active.chunkId;
          const pct = Math.min(100, Math.max(0, Math.round(((score ?? 0) / max) * 100)));
          return (
            <li key={c.chunkId} className="border-b border-border last:border-b-0">
              <button
                type="button"
                aria-pressed={on}
                onClick={() => setSelected(c.chunkId)}
                className={cn(
                  'grid w-full cursor-pointer grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-x-3 px-3 py-2.5 text-left transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring sm:grid-cols-[28px_minmax(0,1fr)_120px_156px]',
                  on ? 'bg-primary-soft/55' : 'hover:bg-muted/65',
                )}
              >
                <span className="font-mono text-xs tabular-nums text-muted-foreground">#{i + 1}</span>
                <span className="min-w-0">
                  <span className="block truncate text-[13px] font-medium text-foreground">
                    {c.title ?? 'Untitled document'}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {c.sectionPath.length > 0 ? c.sectionPath.join(' › ') : c.chunkType}
                  </span>
                </span>
                <span aria-hidden className="hidden h-1 overflow-hidden rounded-full bg-border sm:block">
                  <motion.span
                    initial={reduced ? false : { scaleX: 0 }}
                    animate={{ scaleX: pct / 100 }}
                    transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                    className="block h-full w-full origin-left rounded-full bg-primary"
                  />
                </span>
                <span className="flex items-center justify-end gap-2">
                  <span className="font-mono text-xs tabular-nums text-foreground">
                    {score !== null ? score.toFixed(digits) : '–'}
                  </span>
                  {c.inContext ? (
                    <Badge variant="success">In context</Badge>
                  ) : stageKind === 'chunks-rrf' && c.inPool ? (
                    <Badge variant="info">In pool</Badge>
                  ) : (stageKind === 'chunks-dense' || stageKind === 'chunks-bm25') && c.source === 'alt' ? (
                    <Badge variant="info">Translated</Badge>
                  ) : (stageKind === 'chunks-dense' || stageKind === 'chunks-bm25') && c.source === 'both' ? (
                    <Badge variant="info">Orig + Alt</Badge>
                  ) : (
                    <Badge variant="default">Candidate</Badge>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">{active.title ?? 'Untitled document'}</h3>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setTextMode('formatted')}
                className={cn(
                  'cursor-pointer rounded-md px-2 py-0.5 font-medium transition-colors',
                  textMode === 'formatted' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                Formatted
              </button>
              <button
                type="button"
                onClick={() => setTextMode('raw')}
                className={cn(
                  'cursor-pointer rounded-md px-2 py-0.5 font-medium transition-colors',
                  textMode === 'raw' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                Raw
              </button>
            </div>
            <CopyButton text={active.content} label="Copy" />
          </div>
        </div>

        {stageKind === 'chunks-dense' || stageKind === 'chunks-bm25' ? (
          <dl className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <div className="rounded-lg border border-primary/35 bg-primary-soft/50 px-2.5 py-1.5">
              <dt className="text-xs font-medium text-primary-strong">
                {stageKind === 'chunks-dense' ? 'Cosine similarity' : 'BM25 score'}
              </dt>
              <dd className="font-mono text-[13px] tabular-nums text-foreground">
                {active[metric] !== null ? active[metric]!.toFixed(digits) : '–'}
              </dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              <dt className="text-xs text-muted-foreground">Stage rank</dt>
              <dd className="font-mono text-[13px] tabular-nums text-foreground">
                #{active.rank} / {sorted.length}
              </dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              <dt className="text-xs text-muted-foreground">Query branch</dt>
              <dd className="font-mono text-[13px] text-foreground">
                {active.source === 'alt'
                  ? 'Translated'
                  : active.source === 'both'
                    ? 'Original + Translated'
                    : 'Original'}
              </dd>
            </div>
          </dl>
        ) : stageKind === 'chunks-rrf' ? (
          <dl className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-lg border border-primary/35 bg-primary-soft/50 px-2.5 py-1.5">
              <dt className="text-xs font-medium text-primary-strong">Merged (RRF)</dt>
              <dd className="font-mono text-[13px] tabular-nums text-foreground">
                {active.fusionScore !== null ? active.fusionScore.toFixed(4) : '–'}
              </dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              <dt className="text-xs text-muted-foreground">Dense</dt>
              <dd className="font-mono text-[13px] tabular-nums text-foreground">
                {active.denseScore !== null ? active.denseScore.toFixed(4) : '–'}
              </dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              <dt className="text-xs text-muted-foreground">BM25</dt>
              <dd className="font-mono text-[13px] tabular-nums text-foreground">
                {active.bm25Score !== null ? active.bm25Score.toFixed(2) : '–'}
              </dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2.5 py-1.5">
              <dt className="text-xs text-muted-foreground">Rerank pool</dt>
              <dd className="font-mono text-[13px] text-foreground">
                {active.inPool ? 'Selected' : 'Not selected'}
              </dd>
            </div>
          </dl>
        ) : (
          <dl className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(
              [
                ['Rerank', active.rerankScore, 3, 'rerankScore'],
                ['Merged', active.fusionScore, 4, 'fusionScore'],
                ['Dense', active.denseScore, 4, 'denseScore'],
                ['BM25', active.bm25Score, 2, 'bm25Score'],
              ] as const
            ).map(([label, v, d, key]) => {
              const isPrimary = key === metric;
              return (
                <div
                  key={label}
                  className={cn(
                    'rounded-lg px-2.5 py-1.5',
                    isPrimary ? 'border border-primary/35 bg-primary-soft/50' : 'bg-muted/60',
                  )}
                >
                  <dt className={cn('text-xs', isPrimary ? 'font-medium text-primary-strong' : 'text-muted-foreground')}>
                    {label}
                  </dt>
                  <dd className="font-mono text-[13px] tabular-nums text-foreground">
                    {v !== null ? v.toFixed(d) : '–'}
                  </dd>
                </div>
              );
            })}
          </dl>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          {active.sectionPath.length > 0 ? `${active.sectionPath.join(' › ')} · ` : ''}
          {active.page !== null ? `Page ${active.page} · ` : ''}
          {active.tokenCount} tokens · {active.inContext ? 'in context' : 'candidate only'}
          {active.docCodeMatch ? ' · doc-code boost' : ''}
        </p>

        <div className="mt-2 max-h-72 overflow-y-auto rounded-lg border border-border bg-card p-3.5 text-sm text-foreground">
          {textMode === 'formatted' ? (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <SafeMarkdown text={active.content} />
            </div>
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground">
              {active.content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

function PromptView({
  messages,
  promptVersion,
  model,
  promptTokens,
}: {
  messages: PromptMessageTrace[];
  promptVersion?: string;
  model?: string | null;
  promptTokens?: number | null;
}) {
  const [view, setView] = useState<'structured' | 'raw'>('structured');
  const system = messages.find((m) => m.role === 'system')?.content ?? '';
  const user = messages.find((m) => m.role === 'user')?.content ?? '';
  const cut = system.indexOf('<source');
  const rules = cut >= 0 ? system.slice(0, cut).trim() : system;
  const sources = cut >= 0 ? system.slice(cut).trim() : '';

  const block = (title: string, body: string) => (
    <section>
      <h3 className="mb-1.5 text-[13px] font-medium text-foreground">{title}</h3>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 font-mono text-xs leading-[1.6] text-foreground">
        {body}
      </pre>
    </section>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {promptVersion ? <Badge variant="default">Prompt {promptVersion}</Badge> : null}
          <Badge variant="default">{model ? `Modal · ${model}` : 'Modal (self-hosted)'}</Badge>
          {promptTokens != null ? <Badge variant="default">~{promptTokens.toLocaleString()} tokens</Badge> : null}
          <Badge variant="success">Canary redacted</Badge>
        </div>
        <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setView('structured')}
            className={cn(
              'cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors',
              view === 'structured' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            Structured
          </button>
          <button
            type="button"
            onClick={() => setView('raw')}
            className={cn(
              'cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors',
              view === 'raw' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            Raw messages
          </button>
        </div>
      </div>

      {view === 'structured' ? (
        <div className="space-y-4">
          {user ? block('User message', user) : null}
          {rules ? block('System instructions', rules) : null}
          {sources ? block('Sources in the prompt', sources) : null}
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map((m, i) => (
            <div key={i}>{block(m.role === 'system' ? 'System' : m.role === 'user' ? 'User' : m.role, m.content)}</div>
          ))}
        </div>
      )}
    </div>
  );
}

export function InspectorDetailModal({
  target,
  onClose,
}: {
  target: InspectorModalTarget | null;
  onClose: () => void;
}) {
  if (!target) {
    return (
      <Modal open={false} onClose={onClose}>
        {null}
      </Modal>
    );
  }

  let title = '';
  let description = '';
  let content: React.ReactNode = null;
  let footerLeft: React.ReactNode = null;

  if (target.kind === 'prompt') {
    title = 'Final prompt';
    description = 'The exact messages sent to the answer model, with the per-request canary removed.';
    content = (
      <PromptView
        messages={target.messages}
        promptVersion={target.promptVersion}
        model={target.model}
        promptTokens={target.promptTokens}
      />
    );
    footerLeft = (
      <CopyButton
        text={target.messages.map((m) => `[${m.role}]\n${m.content}`).join('\n\n')}
        label="Copy prompt"
      />
    );
  } else if (target.kind === 'raw') {
    const rawJson = JSON.stringify(target.trace, null, 2);
    title = 'Raw pipeline trace';
    description = 'Sanitized trace for this answer, as JSON.';
    content = (
      <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg bg-muted/60 p-3 font-mono text-xs leading-[1.6] text-foreground">
        {rawJson}
      </pre>
    );
    footerLeft = <CopyButton text={rawJson} label="Copy JSON" />;
  } else {
    const d = CHUNK_DIALOG[target.kind];
    const matchingCount = target.chunks.filter((c) => c[d.metric] !== null).length || target.chunks.length;
    title = `${d.title} (${matchingCount})`;
    description = d.description;
    content = <ChunkExplorer key={target.kind} chunks={target.chunks} stageKind={target.kind} />;
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={title}
      description={description}
      footer={
        <div className="flex items-center justify-between gap-2">
          <div>{footerLeft}</div>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      {content}
    </Modal>
  );
}
