'use client';

import { useMemo, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Badge, Button } from '@/components/ui';
import type { AnswerWarning, Citation } from '@/lib/api/types';
import { refusalCopy, warningText } from '@/lib/chat/labels';
import { canOpenViewer } from '@/lib/chat/citations';
import { CitationViewerModal } from '@/components/viewer/CitationViewerModal';
import { SafeMarkdown } from '@/components/viewer/SafeMarkdown';
import { AnswerMarkdown } from './AnswerMarkdown';
import { FeedbackBar } from './FeedbackBar';
import { ReasoningBlock } from './ReasoningBlock';

export type AnswerCitation = Citation & { isCurrentVersion?: boolean };

export interface AnswerBlockProps {
  text: string;
  citations: AnswerCitation[];
  refusal: { reason: string; nearest: { documentId: string; title: string }[] } | null;
  warnings: AnswerWarning[];
  streaming: boolean;
  /** The model's reasoning so far and how long it took (null while still thinking). */
  reasoning?: string;
  reasoningMs?: number | null;
  /** Feedback needs a persisted assistant message. */
  messageId: string | null;
  children?: React.ReactNode;
}

export function AnswerBlock({
  text,
  citations,
  refusal,
  warnings,
  streaming,
  reasoning = '',
  reasoningMs = null,
  messageId,
  children,
}: AnswerBlockProps) {
  const [openN, setOpenN] = useState<number | null>(null);
  const [viewing, setViewing] = useState<AnswerCitation | null>(null);
  const known = useMemo(() => new Set(citations.map((c) => c.n)), [citations]);
  const thinking = streaming && !text && reasoningMs === null;

  if (refusal) {
    const copy = refusalCopy(refusal.reason);
    return (
      <div className="rounded-lg border border-border border-l-4 border-l-muted-foreground bg-card p-4">
        <Badge variant="neutral">{copy.badge}</Badge>
        <h3 className="mt-2 text-base font-semibold">{copy.title}</h3>
        {text ? (
          <div className="mt-1 text-muted-foreground">
            <AnswerMarkdown text={text} known={known} onCite={() => undefined} />
          </div>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">{copy.body}</p>
        )}
        {copy.showNearest && refusal.nearest.length > 0 ? (
          <div className="mt-3">
            <p className="text-sm text-muted-foreground">Closest documents:</p>
            <ul className="mt-1 flex flex-wrap gap-2">
              {refusal.nearest.map((d) => (
                <li key={d.documentId} className="rounded-full border border-primary bg-primary-soft px-3 py-0.5 text-sm text-primary-strong">
                  {d.title}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {children}
        {messageId && !streaming ? <FeedbackBar messageId={messageId} /> : null}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      {reasoning || thinking ? <ReasoningBlock text={reasoning} durationMs={reasoningMs} thinking={thinking} /> : null}
      {text ? (
        <AnswerMarkdown text={text} known={known} onCite={(n) => setOpenN((cur) => (cur === n ? null : n))} />
      ) : thinking || reasoning ? null : (
        <p className="text-sm text-muted-foreground">Searching your documents…</p>
      )}
      {streaming && text ? (
        <span aria-hidden className="inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />
      ) : null}
      {warnings.map((w) => (
        <div key={w.code} role="note" className="mt-3 flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-foreground">
          <AlertTriangle size={16} aria-hidden className="mt-0.5 shrink-0" />
          <span>{warningText(w)}</span>
        </div>
      ))}
      {citations.length > 0 ? (
        <ul aria-label="Sources" className="mt-3 grid gap-2 sm:grid-cols-2">
          {citations.map((c) => {
            const old = !canOpenViewer(c);
            return (
              <li key={c.n} className="rounded-md border border-border bg-muted p-2 text-sm">
                <button
                  type="button"
                  aria-expanded={openN === c.n}
                  onClick={() => setOpenN((cur) => (cur === c.n ? null : c.n))}
                  className="block w-full text-left focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <span className="font-semibold">
                    [{c.n}] {c.title}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {c.page ? `page ${c.page}` : 'no page'}
                    {old ? ' · stored passage only' : ''}
                  </span>
                </button>
                {old ? (
                  <Badge variant="warning" className="mt-1">
                    Old version
                  </Badge>
                ) : null}
                {openN === c.n ? (
                  <>
                    <div className="prose prose-sm mt-2 max-h-72 max-w-none overflow-auto border-l-2 border-primary pl-3 text-muted-foreground prose-p:my-1.5 prose-headings:my-2 prose-headings:text-foreground prose-table:text-xs">
                      <SafeMarkdown text={c.snippet} />
                    </div>
                    {!old ? (
                      <Button size="sm" variant="outline" className="mt-2" onClick={() => setViewing(c)}>
                        Open in document
                      </Button>
                    ) : null}
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {children}
      {messageId && !streaming ? <FeedbackBar messageId={messageId} /> : null}
      <CitationViewerModal citation={viewing && canOpenViewer(viewing) ? viewing : null} onClose={() => setViewing(null)} />
    </div>
  );
}
