'use client';

import { useState } from 'react';
import { Check, Code2, Copy, FileText, Layers, ShieldCheck, Sparkles } from 'lucide-react';
import { Badge, Button, Modal } from '@/components/ui';
import { SafeMarkdown } from '@/components/viewer/SafeMarkdown';
import type { PipelineTrace, PromptMessageTrace, RetrievedChunkTrace } from '@/lib/api/types';

export type ChunkMetric = 'dense' | 'bm25' | 'fusion' | 'rerank';

export type InspectorModalTarget =
  | {
      kind: 'chunks';
      chunks: RetrievedChunkTrace[];
      initialChunkId?: string;
      title?: string;
      description?: string;
      primaryMetric?: ChunkMetric;
    }
  | { kind: 'chunk'; chunk: RetrievedChunkTrace }
  | {
      kind: 'prompt';
      messages: PromptMessageTrace[];
      promptVersion?: string;
      model?: string | null;
      promptTokens?: number | null;
    }
  | { kind: 'raw'; trace: PipelineTrace };

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
      icon={copied ? <Check size={13} aria-hidden /> : <Copy size={13} aria-hidden />}
      onClick={() => void onCopy()}
    >
      {copied ? 'Copied' : label}
    </Button>
  );
}

function ScoreCell({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-xl border border-border bg-muted/45 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-mono text-sm font-semibold text-foreground">
        {value !== null ? value.toFixed(4) : '—'}
      </div>
    </div>
  );
}

function parseSystemPrompt(systemContent: string): { rules: string; sources: { attrs: string; body: string }[] } {
  const firstMatch = /^<source\s+n="\d+"[^>]*>/m.exec(systemContent);
  if (!firstMatch || firstMatch.index === undefined) return { rules: systemContent.trim(), sources: [] };
  const rules = systemContent.slice(0, firstMatch.index).trim();
  const rest = systemContent.slice(firstMatch.index);
  const sources: { attrs: string; body: string }[] = [];
  const regex = /^<source\s+(n="\d+"[^>]*)>([\s\S]*?)<\/source>/gm;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(rest)) !== null) {
    sources.push({ attrs: match[1].trim(), body: match[2].trim() });
  }
  return { rules, sources };
}

function ChunkModalBody({ chunk }: { chunk: RetrievedChunkTrace }) {
  const [mode, setMode] = useState<'formatted' | 'raw'>('formatted');

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={chunk.inContext ? 'success' : 'default'}>
          {chunk.inContext ? 'Selected for Context' : 'Candidate Only'}
        </Badge>
        <Badge variant="default">{chunk.chunkType}</Badge>
        {chunk.page !== null ? <Badge variant="default">Page {chunk.page}</Badge> : null}
        <Badge variant="default">{chunk.tokenCount} tokens</Badge>
        {chunk.docCodeMatch ? <Badge variant="info">Doc code boost</Badge> : null}
      </div>

      {chunk.sectionPath.length > 0 ? (
        <div className="rounded-xl border border-border/80 bg-muted/35 px-3.5 py-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Section: </span>
          {chunk.sectionPath.join(' › ')}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <ScoreCell label="Rerank" value={chunk.rerankScore} />
        <ScoreCell label="RRF Fusion" value={chunk.fusionScore} />
        <ScoreCell label="Dense Cosine" value={chunk.denseScore} />
        <ScoreCell label="BM25 Lexical" value={chunk.bm25Score} />
      </div>

      <div className="flex items-center justify-between gap-2 border-b border-border/70 pb-2">
        <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setMode('formatted')}
            className={`cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors ${
              mode === 'formatted' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Formatted
          </button>
          <button
            type="button"
            onClick={() => setMode('raw')}
            className={`cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors ${
              mode === 'raw' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Raw Text
          </button>
        </div>
        <CopyButton text={chunk.content} label="Copy chunk" />
      </div>

      {mode === 'formatted' ? (
        <div className="prose prose-sm max-w-none rounded-xl border border-border bg-card p-4 text-sm text-foreground dark:prose-invert">
          <SafeMarkdown text={chunk.content} />
        </div>
      ) : (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl border border-border bg-muted/40 p-4 font-mono text-xs leading-relaxed text-foreground">
          {chunk.content}
        </pre>
      )}
    </div>
  );
}

function PromptModalBody({
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
  const systemMsg = messages.find((m) => m.role === 'system')?.content ?? '';
  const userMsg = messages.find((m) => m.role === 'user')?.content ?? '';
  const parsed = parseSystemPrompt(systemMsg);
  const fullPlain = messages.map((m) => `[${m.role.toUpperCase()}]\n${m.content}`).join('\n\n---\n\n');

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {promptVersion ? <Badge variant="info">Prompt {promptVersion}</Badge> : null}
          {model ? (
            <Badge variant="default" icon={<Sparkles size={11} aria-hidden />}>
              Modal · {model}
            </Badge>
          ) : null}
          {promptTokens != null ? <Badge variant="default">~{promptTokens.toLocaleString()} tokens</Badge> : null}
          <Badge variant="success" icon={<ShieldCheck size={11} aria-hidden />}>
            Canary Redacted
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-border bg-muted/50 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setView('structured')}
              className={`cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors ${
                view === 'structured'
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Structured
            </button>
            <button
              type="button"
              onClick={() => setView('raw')}
              className={`cursor-pointer rounded-md px-2.5 py-1 font-medium transition-colors ${
                view === 'raw' ? 'bg-card text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Raw Messages
            </button>
          </div>
          <CopyButton text={fullPlain} label="Copy prompt" />
          <CopyButton text={JSON.stringify(messages, null, 2)} label="Copy JSON" />
        </div>
      </div>

      {view === 'structured' ? (
        <div className="space-y-4">
          <section className="rounded-xl border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border/70 bg-muted/40 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <FileText size={13} aria-hidden className="text-primary" />
              <span>User Message</span>
            </div>
            <pre className="whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-foreground">{userMsg}</pre>
          </section>

          <section className="rounded-xl border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border/70 bg-muted/40 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <ShieldCheck size={13} aria-hidden className="text-primary" />
              <span>System Instructions</span>
            </div>
            <pre className="whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-foreground">
              {parsed.rules}
            </pre>
          </section>

          {parsed.sources.length > 0 ? (
            <section className="space-y-2.5">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Layers size={13} aria-hidden className="text-primary" />
                <span>Injected Sources ({parsed.sources.length})</span>
              </div>
              {parsed.sources.map((src, idx) => (
                <div key={idx} className="overflow-hidden rounded-xl border border-border bg-card">
                  <div className="border-b border-border/70 bg-primary-soft/45 px-3.5 py-2 font-mono text-[11px] font-medium text-primary-strong">
                    &lt;source {src.attrs}&gt;
                  </div>
                  <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap p-3.5 font-mono text-xs leading-relaxed text-foreground">
                    {src.body}
                  </pre>
                </div>
              ))}
            </section>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((m, idx) => (
            <div key={idx} className="overflow-hidden rounded-xl border border-border bg-card">
              <div className="border-b border-border/70 bg-muted/50 px-3.5 py-1.5 font-mono text-xs font-semibold uppercase text-muted-foreground">
                {m.role}
              </div>
              <pre className="max-h-[46vh] overflow-y-auto whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-foreground">
                {m.content}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChunksExplorerBody({
  chunks,
  initialChunkId,
  primaryMetric = 'rerank',
}: {
  chunks: RetrievedChunkTrace[];
  initialChunkId?: string;
  primaryMetric?: ChunkMetric;
}) {
  const [selectedId, setSelectedId] = useState<string>(
    initialChunkId ?? chunks[0]?.chunkId ?? '',
  );
  const activeIdx = Math.max(0, chunks.findIndex((c) => c.chunkId === selectedId));
  const active = chunks[activeIdx] ?? chunks[0] ?? null;

  if (chunks.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No retrieved chunks available for this stage.
      </p>
    );
  }

  const metricPill = (metric: ChunkMetric, text: string) =>
    primaryMetric === metric ? (
      <span className="rounded bg-primary-soft/85 px-1.5 py-0.5 font-semibold text-primary-strong">{text}</span>
    ) : (
      <span>{text}</span>
    );

  return (
    <div className="grid min-h-[60vh] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      {/* Left pane: selectable chunk list */}
      <div className="flex flex-col gap-2 overflow-y-auto pr-1 lg:max-h-[68vh] lg:border-r lg:border-border/70 lg:pr-3">
        <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
          <span>Chunks ({chunks.length})</span>
          <span>{chunks.filter((c) => c.inContext).length} in context</span>
        </div>
        {chunks.map((ch, idx) => {
          const isSelected = active?.chunkId === ch.chunkId;
          const stageRank = idx + 1;
          return (
            <button
              key={ch.chunkId}
              type="button"
              onClick={() => setSelectedId(ch.chunkId)}
              className={`w-full cursor-pointer rounded-xl border p-2.5 text-left transition-all focus-visible:outline-2 focus-visible:outline-ring ${
                isSelected
                  ? 'border-primary/60 bg-primary-soft/35 ring-1 ring-primary/30'
                  : 'border-border/80 bg-card hover:border-border-strong hover:bg-muted/35'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className="inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded bg-muted px-1 font-mono text-[10px] font-bold text-foreground">
                    #{stageRank}
                  </span>
                  <span className="truncate text-xs font-semibold text-foreground">
                    {ch.title ?? 'Untitled document'}
                  </span>
                </div>
                {ch.inContext ? (
                  <span className="shrink-0 rounded bg-success-soft px-1.5 py-0.5 text-[9px] font-semibold text-success-foreground">
                    In context
                  </span>
                ) : null}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                {ch.page !== null ? <span>p.{ch.page}</span> : null}
                <span>{ch.tokenCount} tok</span>
                {ch.sectionPath.length > 0 ? (
                  <span className="truncate max-w-[170px]">{ch.sectionPath[ch.sectionPath.length - 1]}</span>
                ) : null}
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-foreground">{ch.preview}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
                {ch.rerankScore !== null ? metricPill('rerank', `rerank ${ch.rerankScore.toFixed(3)}`) : null}
                {ch.fusionScore !== null ? metricPill('fusion', `rrf ${ch.fusionScore.toFixed(3)}`) : null}
                {ch.denseScore !== null ? metricPill('dense', `dense ${ch.denseScore.toFixed(3)}`) : null}
                {ch.bm25Score !== null ? metricPill('bm25', `bm25 ${ch.bm25Score.toFixed(2)}`) : null}
              </div>
            </button>
          );
        })}
      </div>

      {/* Right pane: full selected chunk detail */}
      <div className="min-w-0 overflow-y-auto lg:max-h-[68vh] lg:pl-1">
        {active ? (
          <div className="space-y-3">
            <div className="border-b border-border/70 pb-2.5">
              <h3 className="text-sm font-bold text-foreground">
                [#{activeIdx + 1}] {active.title ?? 'Untitled document'}
              </h3>
            </div>
            <ChunkModalBody key={active.chunkId} chunk={active} />
          </div>
        ) : null}
      </div>
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
    return <Modal open={false} onClose={onClose}>{null}</Modal>;
  }

  let title = '';
  let description = '';
  let size: 'xl' | 'full' = 'xl';
  let content: React.ReactNode = null;

  if (target.kind === 'chunks') {
    const inCtx = target.chunks.filter((c) => c.inContext).length;
    title = target.title ?? `Retrieved Chunks (${target.chunks.length})`;
    description =
      target.description ??
      `${inCtx} selected for LLM context · Select any chunk on the left to inspect its full text, metadata, and scores.`;
    size = 'full';
    content = (
      <ChunksExplorerBody
        chunks={target.chunks}
        initialChunkId={target.initialChunkId}
        primaryMetric={target.primaryMetric}
      />
    );
  } else if (target.kind === 'chunk') {
    title = `[#${target.chunk.rank}] ${target.chunk.title ?? 'Untitled document'}`;
    description = 'Full retrieved chunk text, document metadata, and hybrid retrieval scores.';
    content = <ChunkModalBody chunk={target.chunk} />;
  } else if (target.kind === 'prompt') {
    title = 'Final Fusion Prompt (Modal LLM)';
    description = 'Exact system and user messages assembled for the generation model, with the per-request canary redacted.';
    content = (
      <PromptModalBody
        messages={target.messages}
        promptVersion={target.promptVersion}
        model={target.model}
        promptTokens={target.promptTokens}
      />
    );
  } else {
    const rawJson = JSON.stringify(target.trace, null, 2);
    title = 'Raw Pipeline Trace (JSON)';
    description = 'Sanitized execution trace across all pipeline stages.';
    content = (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Badge variant="default" icon={<Code2 size={12} aria-hidden />}>
            Schema v{target.trace.version}
          </Badge>
          <CopyButton text={rawJson} label="Copy JSON" />
        </div>
        <pre className="max-h-[64vh] overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-muted/45 p-4 font-mono text-xs leading-relaxed text-foreground">
          {rawJson}
        </pre>
      </div>
    );
  }

  return (
    <Modal
      open
      onClose={onClose}
      size={size}
      title={title}
      description={description}
      footer={
        <div className="flex justify-end">
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
