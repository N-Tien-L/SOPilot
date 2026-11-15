'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Download, FileText } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Button, Skeleton } from '@/components/ui';
import { getDownloadUrl } from '@/lib/api/endpoints';
import { ApiError } from '@/lib/api/errors';
import { useDocumentContent } from '@/lib/query/hooks';
import { pdfUrlAtPage, READY_MEANING, removedKindLabel, warningLabel } from '@/lib/viewer/labels';
import { citationRange, pageAt, pageSegments, splitByRange } from '@/lib/viewer/offsets';
import { SafeMarkdown } from './SafeMarkdown';

// The recognized content of one document version, shared by the FR-31 screen and the citation
// viewer (FR-14). The Markdown is the canonical text the system indexed; the original PDF is the
// browser's native viewer, loaded on demand through a short-lived signed URL (R5, no PDF library).

export interface CitationHighlight {
  /** Unicode code points on the canonical Markdown, as the citation carries them. */
  charStart: number;
  charEnd: number;
  /** Shown in the banner; the viewer does not open the PDF by itself. */
  n?: number;
  page?: number | null;
}

type Pane = 'text' | 'original';
type TextMode = 'rendered' | 'source';

interface SourceState {
  url: string;
  expiresAt: number;
  page: number | null;
  nonce: number;
}

const URL_REFRESH_MARGIN_MS = 20_000;

export function NotAvailable() {
  return (
    <div role="alert" className="rounded-lg border border-border bg-card p-6 text-center">
      <h2 className="text-base font-semibold">This content is not available</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        It may not be ready yet, it may have been replaced, or you may not have access to it.
      </p>
    </div>
  );
}

function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function ContentViewer({
  documentId,
  versionId,
  originalName,
  highlight = null,
  notice = null,
  fillHeight = false,
}: {
  documentId: string;
  versionId: string;
  originalName?: string;
  highlight?: CitationHighlight | null;
  /** The "Version N is used for Q&A; …" line, when the latest version differs. */
  notice?: string | null;
  /** In a dialog: panes use the available height instead of a viewport-relative one. */
  fillHeight?: boolean;
}) {
  const content = useDocumentContent(documentId, versionId);
  const data = content.data;
  const [pane, setPane] = useState<Pane>('text');
  const [mode, setMode] = useState<TextMode>('rendered');
  const [source, setSource] = useState<SourceState | null>(null);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [sourceError, setSourceError] = useState<unknown>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const nonce = useRef(0);
  const latestAsk = useRef(0);

  const isPdf = data?.fileType?.toUpperCase() === 'PDF';
  const hlStart = highlight?.charStart;
  const hlEnd = highlight?.charEnd;
  const range = useMemo(
    () =>
      data && hlStart !== undefined && hlEnd !== undefined ? citationRange(data.markdown, hlStart, hlEnd) : null,
    [data, hlStart, hlEnd],
  );
  const segments = useMemo(() => (data ? pageSegments(data.markdown.length, data.pages) : []), [data]);
  const highlightedPage = useMemo(() => (data && range ? pageAt(data.pages, range.start) : null), [data, range]);

  // Bring the cited passage into view once the text is there.
  useEffect(() => {
    if (!range || pane !== 'text') return;
    const target = textRef.current?.querySelector<HTMLElement>('[data-highlight="true"]');
    target?.scrollIntoView({ block: 'center' });
  }, [range, pane, mode, data]);

  async function openOriginal(page: number | null) {
    setSourceError(null);
    setPane('original');
    // Reuse the signed URL while it is still valid; otherwise ask again.
    if (source && source.expiresAt - Date.now() > URL_REFRESH_MARGIN_MS) {
      nonce.current += 1;
      setSource({ ...source, page, nonce: nonce.current });
      return;
    }
    // Only the latest ask may open the PDF: a slow earlier answer must not win.
    latestAsk.current += 1;
    const ask = latestAsk.current;
    setSourceBusy(true);
    try {
      const { url, expiresAt } = await getDownloadUrl(documentId, { inline: true });
      if (ask !== latestAsk.current) return;
      nonce.current += 1;
      setSource({ url, expiresAt: Date.parse(expiresAt) || Date.now() + 60_000, page, nonce: nonce.current });
    } catch (e) {
      if (ask === latestAsk.current) setSourceError(e);
    } finally {
      if (ask === latestAsk.current) setSourceBusy(false);
    }
  }

  async function download() {
    setDownloadError(null);
    try {
      const { url } = await getDownloadUrl(documentId);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      setDownloadError(e);
    }
  }

  if (content.isLoading) return <Skeleton count={5} height={28} />;
  if (content.isError) return isNotFound(content.error) ? <NotAvailable /> : <ErrorNote error={content.error} />;
  if (!data) return null;

  const paneHeight = fillHeight ? 'h-[calc(100vh-18rem)] min-h-64' : 'h-[70vh] min-h-80';
  const sharedPageButton =
    'inline-flex items-center rounded-full border border-primary bg-primary-soft px-2.5 py-0.5 text-xs font-semibold text-primary-strong hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring';

  return (
    <div>
      {notice ? (
        <p role="note" className="mb-3 rounded-md bg-info-soft px-3 py-2 text-sm text-info-foreground">
          {notice}
        </p>
      ) : null}
      <p className="mb-3 text-sm text-muted-foreground">{READY_MEANING}</p>

      {data.warnings.map((w, i) => (
        <div key={`${w.code}-${i}`} role="note" className="mb-2 flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-foreground">
          <AlertTriangle size={16} aria-hidden className="mt-0.5 shrink-0" />
          <span>{warningLabel(w)}</span>
        </div>
      ))}

      {highlight && range ? (
        <p role="note" className="mb-3 rounded-md border border-warning bg-warning-soft px-3 py-2 text-sm text-warning-foreground">
          Highlighted: the passage cited{highlight.n ? ` as [${highlight.n}]` : ''}
          {highlight.page ? `, page ${highlight.page}` : highlightedPage ? `, page ${highlightedPage}` : ''}.
        </p>
      ) : highlight ? (
        <p role="note" className="mb-3 text-sm text-muted-foreground">
          The cited passage could not be located in the text, so nothing is highlighted.
        </p>
      ) : null}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {isPdf ? (
          <div role="group" aria-label="View" className="inline-flex rounded-md border border-border bg-muted p-0.5 lg:hidden">
            {(['text', 'original'] as const).map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={pane === p}
                onClick={() => (p === 'original' && !source ? void openOriginal(highlight?.page ?? highlightedPage ?? null) : setPane(p))}
                className={`rounded px-3 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring ${
                  pane === p ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
                }`}
              >
                {p === 'text' ? 'Recognized text' : 'Original PDF'}
              </button>
            ))}
          </div>
        ) : null}
        <div role="group" aria-label="Text display" className="inline-flex rounded-md border border-border bg-muted p-0.5">
          {(['rendered', 'source'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => {
                setMode(m);
                setPane('text');
              }}
              className={`rounded px-3 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring ${
                mode === m ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
              }`}
            >
              {m === 'rendered' ? 'Formatted' : 'Markdown source'}
            </button>
          ))}
        </div>
        <Button size="sm" variant="outline" icon={<Download size={14} aria-hidden />} onClick={() => void download()}>
          Download original{originalName ? ` (${originalName})` : ''}
        </Button>
      </div>
      {downloadError ? <ErrorNote error={downloadError} className="mb-2" /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section
          aria-label="Recognized text"
          className={`${pane === 'text' || !isPdf ? 'block' : 'hidden'} min-w-0 ${isPdf ? '' : 'lg:col-span-2'} lg:block`}
        >
          <div ref={textRef} tabIndex={0} className={`${paneHeight} overflow-auto rounded-lg border border-border bg-card p-4 focus-visible:outline-2 focus-visible:outline-ring`}>
            {mode === 'source' ? (
              <SourceText markdown={data.markdown} range={range} />
            ) : (
              <div className="prose prose-sm max-w-none text-foreground [overflow-wrap:anywhere]">
                {segments.map((seg) => (
                  <div key={`${seg.page ?? 'start'}-${seg.start}`}>
                    {seg.page !== null && isPdf ? (
                      <p className="not-prose my-2">
                        <button type="button" className={sharedPageButton} onClick={() => void openOriginal(seg.page)}>
                          Page {seg.page}
                        </button>
                      </p>
                    ) : null}
                    <SafeMarkdown text={data.markdown.slice(seg.start, seg.end)} baseOffset={seg.start} highlight={range} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {isPdf ? (
          <section aria-label="Original PDF" className={`${pane === 'original' ? 'block' : 'hidden'} min-w-0 lg:block`}>
            <div className={`${paneHeight} overflow-hidden rounded-lg border border-border bg-muted`}>
              {source ? (
                <iframe
                  key={source.nonce}
                  title="Original PDF"
                  src={pdfUrlAtPage(source.url, source.page)}
                  className="h-full w-full bg-card"
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center">
                  <FileText size={28} aria-hidden className="text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    The original file is loaded only when you ask for it.
                  </p>
                  <Button variant="primary" loading={sourceBusy} onClick={() => void openOriginal(highlight?.page ?? highlightedPage ?? null)}>
                    Show original PDF{highlight?.page ?? highlightedPage ? ` at page ${highlight?.page ?? highlightedPage}` : ''}
                  </Button>
                </div>
              )}
            </div>
            {sourceError ? <ErrorNote error={sourceError} className="mt-2" /> : null}
            {sourceBusy && source ? <p className="mt-2 text-xs text-muted-foreground">Loading the original…</p> : null}
          </section>
        ) : null}
      </div>

      {data.removedBlocks.length > 0 ? (
        <details className="mt-4 rounded-lg border border-border bg-card px-4 py-2">
          <summary className="cursor-pointer text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
            Removed repeated blocks ({data.removedBlocks.length})
          </summary>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {data.removedBlocks.map((b, i) => (
              <li key={i}>
                <span className="font-medium text-foreground">{removedKindLabel(b.kind)}</span>
                {b.page ? `, page ${b.page}` : ''}: <span className="[overflow-wrap:anywhere]">{b.text}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

/** The Markdown exactly as stored, with the cited range marked (the only exact-text highlight). */
function SourceText({ markdown, range }: { markdown: string; range: ReturnType<typeof citationRange> }) {
  const { before, hit, after } = splitByRange(markdown, range);
  return (
    <pre className="whitespace-pre-wrap font-mono text-sm [overflow-wrap:anywhere]">
      {before}
      {hit ? (
        <mark data-highlight="true" className="rounded-sm bg-warning-soft text-foreground outline outline-1 outline-warning">
          {hit}
        </mark>
      ) : null}
      {after}
    </pre>
  );
}
