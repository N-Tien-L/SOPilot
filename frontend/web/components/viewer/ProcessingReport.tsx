'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Button, Skeleton } from '@/components/ui';
import { ApiError } from '@/lib/api/errors';
import type { ChunkType, ProcessingReport as Report } from '@/lib/api/types';
import { useDocumentContent, useProcessingChunk, useProcessingReport } from '@/lib/query/hooks';
import { groupChunks, piecesOf, reportPages, type ChunkGroup } from '@/lib/viewer/chunks';
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

// Processing report (V2-46, FR-31): what the system detected, which chunking rules that selects, and one
// page of the canonical Markdown with the chunks outlined. Read only; it follows the same rules as the
// recognized content (READY, access, version), and shows no score.

function Card({ step, title, children }: { step: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 text-lg font-semibold">
        <span className="mr-2 text-muted-foreground">{step}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function DetectedType({ report }: { report: Report }) {
  return (
    <Card step={1} title="Detected type">
      <ul className="space-y-2">
        {FAMILIES.map((f) => {
          const hit = f.id === report.family;
          return (
            <li
              key={f.id}
              aria-current={hit ? 'true' : undefined}
              className={
                hit
                  ? 'rounded-lg border-2 border-green-600 bg-green-500/10 px-3 py-2'
                  : 'rounded-lg border border-dashed border-border px-3 py-2 text-muted-foreground'
              }
            >
              <div className="text-sm font-medium">
                {f.title}
                {hit ? <span className="ml-2 text-xs font-semibold text-green-700 dark:text-green-400">Detected</span> : null}
              </div>
              <div className="text-xs">{f.rule}</div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-sm font-medium">Evidence</p>
      <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
        {signalLines(report).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </Card>
  );
}

function Strategy({ report }: { report: Report }) {
  const { config } = report.strategy;
  return (
    <Card step={2} title="Chunking strategy">
      <p className="mb-2 text-sm text-muted-foreground">
        Selected for <strong>{familyTitle(report.family)}</strong>.
      </p>
      <ol className="space-y-2">
        {report.strategy.rules.map((id) => {
          const r = ruleLabel(id);
          return (
            <li key={id} className="rounded-lg border border-border bg-background px-3 py-2">
              <div className="text-sm font-medium">{r.title}</div>
              {r.detail ? <div className="text-xs text-muted-foreground">{r.detail}</div> : null}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">
        Current configuration: target {config.targetTokens} tokens, at most {config.maxTokens}, sections under{' '}
        {config.minTokens} are merged. A version processed earlier may have used other values.
      </p>
      <p className="mt-3 text-sm font-medium">Other types, for comparison</p>
      <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
        {FAMILIES.filter((f) => f.id !== report.family).map((f) => (
          <li key={f.id}>
            <strong>{f.title}:</strong> {OTHER_FAMILY_NOTES[f.id]}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ChunkDetailPanel({ documentId, versionId, group }: { documentId: string; versionId: string; group: ChunkGroup }) {
  const [ordinal, setOrdinal] = useState(group.ordinals[0]);
  const detail = useProcessingChunk(documentId, versionId, ordinal);
  return (
    <div className="mt-3 rounded-lg border border-border bg-background p-3 text-sm" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <strong>Chunk {group.label}</strong>
        {group.ordinals.length > 1
          ? group.ordinals.map((o) => (
              <Button key={o} size="sm" variant={o === ordinal ? 'primary' : 'outline'} onClick={() => setOrdinal(o)}>
                #{o + 1}
              </Button>
            ))
          : null}
      </div>
      {detail.isLoading ? <Skeleton count={2} height={20} /> : null}
      {detail.isError ? <ErrorNote error={detail.error} /> : null}
      {detail.data ? (
        <>
          <p className="mt-2 text-xs text-muted-foreground">
            {CHUNK_TYPE_LABEL[detail.data.chunkType]} · {detail.data.tokenCount} tokens · {detail.data.sectionPath.join(' › ') || 'no section'}
          </p>
          <p className="mt-2 text-xs font-medium">Text that is embedded and searched</p>
          <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded border border-border bg-card p-2 text-xs [overflow-wrap:anywhere]">
            {detail.data.indexText}
          </pre>
        </>
      ) : null}
    </div>
  );
}

function SamplePage({ report, documentId, versionId }: { report: Report; documentId: string; versionId: string }) {
  const content = useDocumentContent(documentId, versionId);
  const [pageIndex, setPageIndex] = useState(0);
  const [selected, setSelected] = useState<ChunkGroup | null>(null);

  const markdown = content.data?.markdown ?? '';
  const groups = useMemo(() => groupChunks(report.chunks, markdown), [report.chunks, markdown]);
  const pages = useMemo(
    () => reportPages(markdown.length, content.data?.pages ?? [], groups),
    [markdown, content.data?.pages, groups],
  );

  let body: React.ReactNode;
  if (content.isLoading) body = <Skeleton count={6} height={20} />;
  else if (content.isError) body = <ErrorNote error={content.error} />;
  else if (pages.length === 0) body = <p className="text-sm text-muted-foreground">This version has no text to show.</p>;
  else {
    const index = Math.min(pageIndex, pages.length - 1);
    const page = pages[index];
    const pieces = piecesOf(page, groups);
    body = (
      <>
        <div className="mb-2 flex items-center justify-between gap-2">
          <Button
            size="sm"
            variant="outline"
            className="whitespace-nowrap"
            icon={<ChevronLeft size={14} aria-hidden />}
            disabled={index === 0}
            onClick={() => { setPageIndex(index - 1); setSelected(null); }}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground" aria-live="polite">
            {page.label} · {index + 1} of {pages.length}
          </span>
          <Button
            size="sm"
            variant="outline"
            className="whitespace-nowrap"
            disabled={index >= pages.length - 1}
            onClick={() => { setPageIndex(index + 1); setSelected(null); }}
          >
            Next <ChevronRight size={14} aria-hidden />
          </Button>
        </div>
        <div className="max-h-[32rem] overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed">
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
            return (
              <button
                key={`c${p.group.key}-${p.start}`}
                type="button"
                aria-pressed={open}
                aria-label={`Chunk ${p.group.label}, ${CHUNK_TYPE_LABEL[p.group.chunkType]}, ${p.group.tokens} tokens`}
                onClick={() => setSelected(open ? null : p.group)}
                className={`relative my-1 block w-full whitespace-pre-wrap rounded-sm border-2 border-dashed px-2 pb-1 pt-5 text-left text-foreground [overflow-wrap:anywhere] focus-visible:outline-2 focus-visible:outline-ring ${cls.box} ${open ? 'ring-2 ring-ring' : ''}`}
              >
                <span className={`absolute left-2 top-0.5 font-sans text-[11px] font-semibold ${cls.text}`}>
                  {p.group.label} · {CHUNK_TYPE_LABEL[p.group.chunkType]} · {p.group.tokens} tok
                  {p.cutBefore ? ' · continues from the previous page' : ''}
                  {p.cutAfter ? ' · continues on the next page' : ''}
                </span>
                {markdown.slice(p.start, p.end)}
              </button>
            );
          })}
        </div>
        {selected ? <ChunkDetailPanel key={selected.key} documentId={documentId} versionId={versionId} group={selected} /> : null}
      </>
    );
  }

  const types = Object.keys(report.stats.byType) as ChunkType[];
  return (
    <Card step={3} title="Sample page, chunks outlined">
      {body}
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {(['SECTION', 'PROCEDURE_STEP', 'TABLE'] as ChunkType[]).map((t) => (
          <li key={t} className="flex items-center gap-1">
            <span aria-hidden className={`inline-block h-3 w-5 border-2 border-dashed ${chunkTypeClasses(t).swatch}`} />
            {t === 'SECTION' ? 'Section or prose' : CHUNK_TYPE_LABEL[t]}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm">
        Whole document: {report.stats.chunks} chunks, average {report.stats.avgTokens} tokens, largest{' '}
        {report.stats.maxTokens} of {report.strategy.config.maxTokens}.
        {types.length > 0 ? ` ${types.map((t) => `${report.stats.byType[t]} ${CHUNK_TYPE_LABEL[t].toLowerCase()}`).join(', ')}.` : ''}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        The page shows the text the system recognized, not the original file. Click a chunk to see what is embedded.
      </p>
    </Card>
  );
}

export function ProcessingReport({ documentId, versionId }: { documentId: string; versionId: string }) {
  const report = useProcessingReport(documentId, versionId);
  if (report.isLoading) return <Skeleton count={6} height={32} />;
  if (report.isError) {
    return report.error instanceof ApiError && report.error.status === 404 ? <NotAvailable /> : <ErrorNote error={report.error} />;
  }
  if (!report.data) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.5fr)]">
      <DetectedType report={report.data} />
      <Strategy report={report.data} />
      <SamplePage report={report.data} documentId={documentId} versionId={versionId} />
    </div>
  );
}
