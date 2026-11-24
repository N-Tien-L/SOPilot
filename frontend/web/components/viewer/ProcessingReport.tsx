'use client';

import { useId, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FolderTree,
  Layers,
  Search,
  X,
} from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { CountUp, SpotlightCard } from '@/components/effects';
import { Button, Skeleton } from '@/components/ui';
import { ApiError } from '@/lib/api/errors';
import type { ChunkType, ProcessingReport as Report } from '@/lib/api/types';
import { useDocumentContent, useProcessingChunk, useProcessingReport } from '@/lib/query/hooks';
import {
  filterChunkGroups,
  formatPageRange,
  groupChunks,
  piecesOf,
  reportPages,
  type ChunkGroup,
} from '@/lib/viewer/chunks';
import {
  CHUNK_TYPE_LABEL,
  chunkTypeClasses,
  familyTitle,
  FAMILIES,
  OTHER_FAMILY_NOTES,
  ruleLabel,
  signalLines,
} from '@/lib/viewer/report-labels';
import { NotAvailable } from './ContentViewer';

// Processing report (V2-46, FR-31): what the system detected, which chunking rules that selects, and
// the full chunk breakdown (with sectionPath, page range, token budget, and optional by-page view).
// Read only; it follows the same rules as the recognized content (READY, access, version), and shows no score.

const INITIAL_BATCH = 60;

function StepCard({ step, title, subtitle, children }: { step: number; title: string; subtitle?: React.ReactNode; children: React.ReactNode }) {
  return (
    <SpotlightCard className="rounded-2xl p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
            {step}
          </span>
          <span>{title}</span>
        </h2>
        {subtitle}
      </div>
      {children}
    </SpotlightCard>
  );
}

function DetectedType({ report }: { report: Report }) {
  return (
    <StepCard step={1} title="Detected type">
      <ul className="space-y-2">
        {FAMILIES.map((f) => {
          const hit = f.id === report.family;
          return (
            <li
              key={f.id}
              aria-current={hit ? 'true' : undefined}
              className={
                hit
                  ? 'rounded-xl border-2 border-success bg-success-soft/60 px-3.5 py-2.5'
                  : 'rounded-xl border border-dashed border-border px-3.5 py-2 text-muted-foreground opacity-80'
              }
            >
              <div className="flex items-center justify-between gap-2 text-sm font-semibold text-foreground">
                <span>{f.title}</span>
                {hit ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success px-2 py-0.5 text-[11px] font-semibold text-white">
                    <CheckCircle2 size={11} aria-hidden /> Detected
                  </span>
                ) : null}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">{f.rule}</div>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Evidence</p>
      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
        {signalLines(report).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </StepCard>
  );
}

function Strategy({ report }: { report: Report }) {
  const { config } = report.strategy;
  return (
    <StepCard step={2} title="Chunking strategy">
      <p className="mb-3 text-xs text-muted-foreground">
        Selected for <strong className="text-foreground">{familyTitle(report.family)}</strong>.
      </p>
      <div className="mb-3.5 grid grid-cols-3 gap-2">
        <div className="rounded-xl border border-border bg-muted/50 p-2.5">
          <div className="text-[11px] text-muted-foreground">Chunks</div>
          <div className="mt-0.5 text-lg font-bold text-foreground">
            <CountUp to={report.stats.chunks} />
          </div>
        </div>
        <div className="rounded-xl border border-border bg-muted/50 p-2.5">
          <div className="text-[11px] text-muted-foreground">Avg tok</div>
          <div className="mt-0.5 text-lg font-bold text-foreground">
            <CountUp to={report.stats.avgTokens} />
          </div>
        </div>
        <div className="rounded-xl border border-border bg-muted/50 p-2.5">
          <div className="text-[11px] text-muted-foreground">Target</div>
          <div className="mt-0.5 text-lg font-bold text-foreground">
            <CountUp to={config.targetTokens} />
          </div>
        </div>
      </div>
      <ol className="space-y-2">
        {report.strategy.rules.map((id) => {
          const r = ruleLabel(id);
          return (
            <li key={id} className="rounded-xl border border-border bg-background/80 px-3 py-2">
              <div className="text-xs font-semibold text-foreground">{r.title}</div>
              {r.detail ? <div className="mt-0.5 text-xs text-muted-foreground">{r.detail}</div> : null}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">
        Current configuration: target {config.targetTokens} tokens, at most {config.maxTokens}, sections under{' '}
        {config.minTokens} are merged. A version processed earlier may have used other values.
      </p>
      <p className="mt-3.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Other types, for comparison
      </p>
      <ul className="mt-1.5 space-y-1 text-xs text-muted-foreground">
        {FAMILIES.filter((f) => f.id !== report.family).map((f) => (
          <li key={f.id}>
            <strong className="text-foreground">{f.title}:</strong> {OTHER_FAMILY_NOTES[f.id]}
          </li>
        ))}
      </ul>
    </StepCard>
  );
}

function ChunkDetailPanel({
  documentId,
  versionId,
  group,
  onClose,
}: {
  documentId: string;
  versionId: string;
  group: ChunkGroup;
  onClose: () => void;
}) {
  const [ordinal, setOrdinal] = useState(group.ordinals[0]);
  const detail = useProcessingChunk(documentId, versionId, ordinal);
  return (
    <div className="mt-2 rounded-xl border border-primary/40 bg-card p-4 text-sm shadow-sm" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <strong className="text-foreground">Chunk {group.label} · Embedded payload</strong>
          {group.ordinals.length > 1
            ? group.ordinals.map((o) => (
                <Button key={o} size="sm" variant={o === ordinal ? 'primary' : 'outline'} onClick={() => setOrdinal(o)}>
                  #{o + 1}
                </Button>
              ))
            : null}
        </div>
        <button
          type="button"
          aria-label="Close chunk detail"
          onClick={onClose}
          className="cursor-pointer rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={14} aria-hidden />
        </button>
      </div>
      {detail.isLoading ? <Skeleton count={2} height={20} className="mt-2" /> : null}
      {detail.isError ? <ErrorNote error={detail.error} className="mt-2" /> : null}
      {detail.data ? (
        <>
          <p className="mt-2 text-xs text-muted-foreground">
            {CHUNK_TYPE_LABEL[detail.data.chunkType]} · {detail.data.tokenCount} tokens ·{' '}
            {detail.data.sectionPath.join(' › ') || 'no section'}
          </p>
          <p className="mt-2.5 text-xs font-semibold text-foreground">Text that is embedded and searched</p>
          <pre className="mt-1.5 max-h-60 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-background p-3 font-mono text-xs leading-relaxed text-foreground [overflow-wrap:anywhere]">
            {detail.data.indexText}
          </pre>
        </>
      ) : null}
    </div>
  );
}

function TokenBar({ tokens, target, max }: { tokens: number; target: number; max: number }) {
  const denom = Math.max(max, target, 1);
  const pct = Math.min(100, Math.round((tokens / denom) * 100));
  const tone = tokens > max ? 'bg-danger' : tokens > target ? 'bg-warning' : 'bg-primary';
  return (
    <span className="inline-flex items-center gap-1.5" title={`${tokens} tokens (target ${target}, max ${max})`}>
      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-border/80" aria-hidden>
        <span className={`block h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono text-[11px] font-medium text-muted-foreground">
        {tokens} / {target} tok
      </span>
    </span>
  );
}

function AllChunksExplorer({ report, documentId, versionId }: { report: Report; documentId: string; versionId: string }) {
  const toggleId = useId();
  const content = useDocumentContent(documentId, versionId);
  const [view, setView] = useState<'all' | 'page'>('all');
  const [typeFilter, setTypeFilter] = useState<ChunkType | 'ALL'>('ALL');
  const [query, setQuery] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [selected, setSelected] = useState<ChunkGroup | null>(null);
  const [visibleLimit, setVisibleLimit] = useState(INITIAL_BATCH);

  const markdown = content.data?.markdown ?? '';
  const groups = useMemo(() => groupChunks(report.chunks, markdown), [report.chunks, markdown]);
  const pages = useMemo(
    () => reportPages(markdown.length, content.data?.pages ?? [], groups),
    [markdown, content.data?.pages, groups],
  );
  const filtered = useMemo(
    () => filterChunkGroups(groups, markdown, { type: typeFilter, query }),
    [groups, markdown, typeFilter, query],
  );

  const typeCounts = useMemo(() => {
    const counts: Partial<Record<ChunkType, number>> = {};
    for (const g of groups) {
      counts[g.chunkType] = (counts[g.chunkType] ?? 0) + 1;
    }
    return counts;
  }, [groups]);

  const presentTypes = (['SECTION', 'PROCEDURE_STEP', 'TABLE', 'PROSE'] as ChunkType[]).filter(
    (t) => (typeCounts[t] ?? 0) > 0,
  );
  const { targetTokens, maxTokens } = report.strategy.config;
  const shown = filtered.slice(0, visibleLimit);

  let body: React.ReactNode;
  if (content.isLoading) {
    body = <Skeleton count={6} height={44} />;
  } else if (content.isError) {
    body = <ErrorNote error={content.error} />;
  } else if (groups.length === 0) {
    body = <p className="text-sm text-muted-foreground">This version has no chunks to show.</p>;
  } else if (view === 'page') {
    const index = Math.min(pageIndex, Math.max(pages.length - 1, 0));
    const page = pages[index];
    const pieces = page ? piecesOf(page, groups) : [];
    body = (
      <>
        <div className="mb-3 flex items-center justify-between gap-2">
          <Button
            size="sm"
            variant="outline"
            icon={<ChevronLeft size={14} aria-hidden />}
            disabled={index === 0}
            onClick={() => {
              setPageIndex(index - 1);
              setSelected(null);
            }}
          >
            Previous
          </Button>
          <span className="text-xs font-medium text-muted-foreground" aria-live="polite">
            {page?.label} · {index + 1} of {pages.length}
          </span>
          <Button
            size="sm"
            variant="outline"
            icon={<ChevronRight size={14} aria-hidden />}
            iconPosition="right"
            disabled={index >= pages.length - 1}
            onClick={() => {
              setPageIndex(index + 1);
              setSelected(null);
            }}
          >
            Next
          </Button>
        </div>
        <div className="max-h-[38rem] overflow-auto rounded-xl border border-border bg-background p-3.5 font-mono text-xs leading-relaxed">
          {pieces.map((p) => {
            if (p.type === 'text') {
              return (
                <span key={`t${p.start}`} className="whitespace-pre-wrap text-muted-foreground [overflow-wrap:anywhere]">
                  {markdown.slice(p.start, p.end)}
                </span>
              );
            }
            const cls = chunkTypeClasses(p.group.chunkType);
            const open = selected?.key === p.group.key;
            const pageLabel = formatPageRange(p.group.pageStart, p.group.pageEnd);
            return (
              <div key={`c${p.group.key}-${p.start}`} className="my-2">
                <button
                  type="button"
                  aria-pressed={open}
                  aria-label={`Chunk ${p.group.label}, ${CHUNK_TYPE_LABEL[p.group.chunkType]}, ${p.group.tokens} tokens`}
                  onClick={() => setSelected(open ? null : p.group)}
                  className={`block w-full cursor-pointer whitespace-pre-wrap rounded-xl border-2 border-dashed px-3 py-2.5 text-left text-foreground transition-shadow [overflow-wrap:anywhere] focus-visible:outline-2 focus-visible:outline-ring ${cls.box} ${open ? 'ring-2 ring-ring' : ''}`}
                >
                  <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2 font-sans">
                    <span className={`text-[11px] font-semibold ${cls.text}`}>
                      {p.group.label} · {CHUNK_TYPE_LABEL[p.group.chunkType]}
                      {pageLabel ? ` · ${pageLabel}` : ''}
                      {p.cutBefore ? ' · continues from prev' : ''}
                      {p.cutAfter ? ' · continues on next' : ''}
                    </span>
                    <TokenBar tokens={p.group.tokens} target={targetTokens} max={maxTokens} />
                  </div>
                  {p.group.sectionPath.length > 0 ? (
                    <div className="mb-1.5 flex items-center gap-1.5 font-sans text-[11px] text-muted-foreground">
                      <FolderTree size={11} aria-hidden className="shrink-0 text-primary" />
                      <span className="truncate">{p.group.sectionPath.join(' › ')}</span>
                    </div>
                  ) : null}
                  <div>{markdown.slice(p.start, p.end)}</div>
                </button>
                {open ? (
                  <ChunkDetailPanel
                    key={p.group.key}
                    documentId={documentId}
                    versionId={versionId}
                    group={p.group}
                    onClose={() => setSelected(null)}
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      </>
    );
  } else {
    body = (
      <div className="space-y-3">
        {/* Search & Type Filter Bar */}
        <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-border bg-background/70 p-2.5">
          <div className="relative min-w-[200px] flex-1">
            <Search size={14} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              aria-label="Filter chunks by section path or text"
              placeholder="Search section path, chunk # or text…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setVisibleLimit(INITIAL_BATCH);
              }}
              className="h-9 w-full rounded-lg border border-input bg-card pl-8 pr-3 text-xs text-foreground placeholder:text-placeholder outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by chunk type">
            <button
              type="button"
              aria-pressed={typeFilter === 'ALL'}
              onClick={() => setTypeFilter('ALL')}
              className={`cursor-pointer rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
                typeFilter === 'ALL'
                  ? 'bg-primary text-primary-foreground'
                  : 'border border-border bg-card text-muted-foreground hover:text-foreground'
              }`}
            >
              All ({groups.length})
            </button>
            {presentTypes.map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={typeFilter === t}
                onClick={() => setTypeFilter(t)}
                className={`cursor-pointer rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
                  typeFilter === t
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-border bg-card text-muted-foreground hover:text-foreground'
                }`}
              >
                {CHUNK_TYPE_LABEL[t]} ({typeCounts[t]})
              </button>
            ))}
          </div>
        </div>

        {filtered.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No chunks match this filter.
          </p>
        ) : (
          <div className="max-h-[46rem] space-y-2.5 overflow-y-auto pr-1">
            {shown.map((g) => {
              const cls = chunkTypeClasses(g.chunkType);
              const open = selected?.key === g.key;
              const pageLabel = formatPageRange(g.pageStart, g.pageEnd);
              return (
                <div key={g.key}>
                  <button
                    type="button"
                    aria-pressed={open}
                    aria-label={`Chunk ${g.label}, ${CHUNK_TYPE_LABEL[g.chunkType]}, ${g.tokens} tokens`}
                    onClick={() => setSelected(open ? null : g)}
                    className={`block w-full cursor-pointer rounded-xl border-2 border-dashed p-3.5 text-left transition-all focus-visible:outline-2 focus-visible:outline-ring ${cls.box} ${open ? 'ring-2 ring-ring' : 'hover:brightness-[0.98]'}`}
                  >
                    {/* Header metadata row */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`font-mono text-xs font-bold ${cls.text}`}>{g.label}</span>
                        <span className="rounded-md border border-border/80 bg-card/80 px-2 py-0.5 text-[11px] font-semibold text-foreground">
                          {CHUNK_TYPE_LABEL[g.chunkType]}
                        </span>
                        {pageLabel ? (
                          <span className="rounded-md bg-primary-soft px-2 py-0.5 font-mono text-[11px] font-semibold text-primary-strong">
                            {pageLabel}
                          </span>
                        ) : null}
                        <span className="font-mono text-[11px] text-muted-foreground">
                          chars {g.charStart}–{g.charEnd}
                        </span>
                      </div>
                      <TokenBar tokens={g.tokens} target={targetTokens} max={maxTokens} />
                    </div>

                    {/* Section path breadcrumb */}
                    <div className="mt-2 flex items-center gap-1.5 rounded-lg bg-card/70 px-2.5 py-1 text-xs">
                      <FolderTree size={12} aria-hidden className="shrink-0 text-primary" />
                      {g.sectionPath.length > 0 ? (
                        <span className="font-medium text-foreground [overflow-wrap:anywhere]">
                          {g.sectionPath.join(' › ')}
                        </span>
                      ) : (
                        <span className="italic text-muted-foreground">Root (no heading path)</span>
                      )}
                    </div>

                    {/* Chunk Markdown text */}
                    <div className="mt-2.5 whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground [overflow-wrap:anywhere]">
                      {markdown.slice(g.start, g.end)}
                    </div>
                  </button>

                  {open ? (
                    <ChunkDetailPanel
                      key={g.key}
                      documentId={documentId}
                      versionId={versionId}
                      group={g}
                      onClose={() => setSelected(null)}
                    />
                  ) : null}
                </div>
              );
            })}

            {filtered.length > visibleLimit ? (
              <div className="flex items-center justify-center gap-2 pt-2">
                <Button size="sm" variant="outline" onClick={() => setVisibleLimit((n) => n + INITIAL_BATCH)}>
                  Show {Math.min(INITIAL_BATCH, filtered.length - visibleLimit)} more
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setVisibleLimit(filtered.length)}>
                  Show all {filtered.length} chunks
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    );
  }

  const types = Object.keys(report.stats.byType) as ChunkType[];
  return (
    <StepCard
      step={3}
      title="All chunks"
      subtitle={
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Layers size={13} aria-hidden className="text-primary" />
            {groups.length} {groups.length === 1 ? 'outline' : 'outlines'} ({report.stats.chunks} chunks)
          </span>
          <div role="group" aria-label="Chunk view mode" className="inline-flex rounded-xl border border-border bg-muted p-0.5">
            {(
              [
                { id: 'all', label: 'All chunks' },
                { id: 'page', label: 'By page' },
              ] as const
            ).map((opt) => (
              <button
                key={opt.id}
                type="button"
                aria-pressed={view === opt.id}
                onClick={() => {
                  setView(opt.id);
                  setSelected(null);
                }}
                className={`relative cursor-pointer rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
                  view === opt.id ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {view === opt.id ? (
                  <motion.span
                    layoutId={`chunks-view-${toggleId}`}
                    className="absolute inset-0 rounded-lg bg-card shadow-xs"
                    transition={{ type: 'spring', stiffness: 450, damping: 34 }}
                  />
                ) : null}
                <span className="relative z-10">{opt.label}</span>
              </button>
            ))}
          </div>
        </div>
      }
    >
      {body}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border/70 pt-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {(['SECTION', 'PROCEDURE_STEP', 'TABLE'] as ChunkType[]).map((t) => (
            <li key={t} className="flex items-center gap-1.5">
              <span aria-hidden className={`inline-block h-3 w-5 rounded-xs border-2 border-dashed ${chunkTypeClasses(t).swatch}`} />
              {t === 'SECTION' ? 'Section or prose' : CHUNK_TYPE_LABEL[t]}
            </li>
          ))}
        </ul>
        <p className="text-xs text-foreground">
          Whole document: <strong>{report.stats.chunks}</strong> chunks · avg <strong>{report.stats.avgTokens}</strong> tok · max{' '}
          <strong>{report.stats.maxTokens}</strong> / {report.strategy.config.maxTokens}
          {types.length > 0
            ? ` (${types.map((t) => `${report.stats.byType[t]} ${CHUNK_TYPE_LABEL[t].toLowerCase()}`).join(', ')})`
            : ''}
        </p>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Click any chunk to inspect the exact prefixed text embedded and indexed for search.
      </p>
    </StepCard>
  );
}

export function ProcessingReport({ documentId, versionId }: { documentId: string; versionId: string }) {
  const report = useProcessingReport(documentId, versionId);
  if (report.isLoading) return <Skeleton count={6} height={36} />;
  if (report.isError) {
    return report.error instanceof ApiError && report.error.status === 404 ? <NotAvailable /> : <ErrorNote error={report.error} />;
  }
  if (!report.data) return null;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <DetectedType report={report.data} />
        <Strategy report={report.data} />
      </div>
      <AllChunksExplorer report={report.data} documentId={documentId} versionId={versionId} />
    </div>
  );
}
