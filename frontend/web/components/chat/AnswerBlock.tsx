'use client';

import { useMemo, useState } from 'react';
import { Activity, AlertTriangle, BookOpen, ExternalLink, FileText, ShieldAlert } from 'lucide-react';
import { Badge, Button } from '@/components/ui';
import { ShinyText } from '@/components/effects';
import { CollapsiblePanel } from '@/components/motion/Primitives';
import type { AnswerWarning, Citation } from '@/lib/api/types';
import { refusalCopy, warningText } from '@/lib/chat/labels';
import { canOpenViewer } from '@/lib/chat/citations';
import { groupCitationsByDocument } from '@/lib/chat/citation-groups';
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
  /** Whether this turn is currently selected in the Pipeline Inspector. */
  inspected?: boolean;
  /** Selects this turn in the Pipeline Inspector side-panel. */
  onInspect?: () => void;
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
  inspected = false,
  onInspect,
  children,
}: AnswerBlockProps) {
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const [viewing, setViewing] = useState<{ citation: AnswerCitation; label?: string } | null>(null);
  const known = useMemo(() => new Set(citations.map((c) => c.n)), [citations]);
  const grouped = useMemo(() => groupCitationsByDocument(citations), [citations]);
  const thinking = streaming && !text && reasoningMs === null;

  function handleInlineCite(n: number) {
    const found = grouped.itemByN.get(n);
    if (!found) return;
    setOpenDoc(found.citation.documentId);
    if (canOpenViewer(found.citation)) {
      setViewing({ citation: found.citation, label: found.label });
    }
  }

  const inspectButton = onInspect ? (
    <button
      type="button"
      onClick={onInspect}
      aria-pressed={inspected}
      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring ${
        inspected
          ? 'border-primary/45 bg-primary-soft text-primary-strong'
          : 'border-border/80 bg-muted/45 text-muted-foreground hover:border-border-strong hover:text-foreground'
      }`}
    >
      <Activity size={12} aria-hidden />
      <span>{inspected ? 'Inspecting pipeline' : 'Inspect pipeline'}</span>
    </button>
  ) : null;

  if (refusal) {
    const copy = refusalCopy(refusal.reason);
    return (
      <div
        className={`rounded-2xl border border-l-4 border-l-warning bg-card p-5 shadow-[var(--shadow-sm)] transition-shadow ${
          inspected ? 'border-primary/50 ring-2 ring-primary/20' : 'border-border'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <Badge variant="warning" icon={<ShieldAlert size={12} aria-hidden />}>
            {copy.badge}
          </Badge>
          {inspectButton}
        </div>
        <h3 className="mt-2.5 text-base font-semibold text-foreground">{copy.title}</h3>
        {text ? (
          <div className="mt-1.5 text-muted-foreground">
            <AnswerMarkdown text={text} known={known} onCite={() => undefined} />
          </div>
        ) : (
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{copy.body}</p>
        )}
        {copy.showNearest && refusal.nearest.length > 0 ? (
          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Closest documents
            </p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {refusal.nearest.map((d) => (
                <li
                  key={d.documentId}
                  className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary-soft px-3 py-1 text-xs font-medium text-primary-strong"
                >
                  <FileText size={12} aria-hidden />
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
    <div
      className={`rounded-2xl border bg-card p-5 shadow-[var(--shadow-sm)] transition-shadow ${
        inspected ? 'border-primary/50 ring-2 ring-primary/20' : 'border-border'
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          {reasoning || thinking ? <ReasoningBlock text={reasoning} durationMs={reasoningMs} thinking={thinking} /> : null}
        </div>
        {inspectButton ? <div className="shrink-0 self-start">{inspectButton}</div> : null}
      </div>
      {text ? (
        <AnswerMarkdown text={text} known={known} labels={grouped.labelByN} onCite={handleInlineCite} />
      ) : thinking || reasoning ? null : (
        <p className="text-sm font-medium">
          <ShinyText active>Searching your documents…</ShinyText>
        </p>
      )}
      {streaming && text ? (
        <span aria-hidden className="ml-0.5 inline-block h-4 w-1.5 rounded-xs bg-primary align-text-bottom animate-pulse" />
      ) : null}
      {warnings.map((w) => (
        <div
          key={w.code}
          role="note"
          className="mt-3.5 flex items-start gap-2 rounded-xl border border-warning/25 bg-warning-soft px-3.5 py-2.5 text-xs text-warning-foreground"
        >
          <AlertTriangle size={15} aria-hidden className="mt-0.5 shrink-0" />
          <span>{warningText(w)}</span>
        </div>
      ))}
      {grouped.groups.length > 0 ? (
        <div className="mt-4 border-t border-border/80 pt-3.5">
          <div className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <BookOpen size={13} aria-hidden className="text-primary" />
            <span>
              Sources ({grouped.groups.length} file{grouped.groups.length === 1 ? '' : 's'} · {citations.length} chunk
              {citations.length === 1 ? '' : 's'})
            </span>
          </div>
          <ul aria-label="Sources" className="grid gap-2.5 sm:grid-cols-2">
            {grouped.groups.map((group) => {
              const expanded = openDoc === group.documentId;
              const allOld = group.items.every((item) => !canOpenViewer(item.citation));
              return (
                <li
                  key={group.documentId}
                  className={`rounded-xl border p-3 text-sm transition-all ${
                    expanded
                      ? 'border-primary/50 bg-primary-soft/30 shadow-xs sm:col-span-2'
                      : 'border-border bg-muted/45 hover:border-border-strong'
                  }`}
                >
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setOpenDoc((cur) => (cur === group.documentId ? null : group.documentId))}
                    className="flex w-full cursor-pointer items-start justify-between gap-2 text-left focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <div className="flex min-w-0 items-start gap-2.5">
                      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-primary-soft font-mono text-[11px] font-bold text-primary-strong">
                        {group.docIndex}
                      </span>
                      <div className="min-w-0">
                        <span className="block truncate font-semibold text-foreground">{group.title}</span>
                        <span className="block text-xs text-muted-foreground">
                          {group.items.length} cited chunk{group.items.length === 1 ? '' : 's'}
                          {allOld ? ' · stored passage only' : ''}
                        </span>
                      </div>
                    </div>
                    {allOld ? (
                      <Badge variant="warning" className="shrink-0">
                        Old version
                      </Badge>
                    ) : null}
                  </button>
                  <CollapsiblePanel open={expanded}>
                    <ul aria-label={`Cited chunks in ${group.title}`} className="mt-3 space-y-2">
                      {group.items.map(({ label, citation: c }) => {
                        const old = !canOpenViewer(c);
                        const section =
                          c.sectionPath && c.sectionPath.length > 0
                            ? c.sectionPath[c.sectionPath.length - 1]
                            : c.chunks && c.chunks[0]?.sectionPath?.length
                              ? c.chunks[0].sectionPath[c.chunks[0].sectionPath.length - 1]
                              : null;
                        return (
                          <li
                            key={c.n}
                            className="rounded-lg border border-border/80 bg-card/90 p-2.5 transition-colors hover:border-primary/45"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex min-w-0 items-center gap-2">
                                <span className="inline-flex shrink-0 items-center justify-center rounded-md bg-primary-soft px-1.5 py-0.5 font-mono text-[11px] font-bold text-primary-strong">
                                  {label}
                                </span>
                                <div className="min-w-0">
                                  {section ? (
                                    <span className="block truncate text-xs font-semibold text-foreground">
                                      {section}
                                    </span>
                                  ) : null}
                                  <span className="block text-[11px] text-muted-foreground">
                                    {c.page !== null ? `Page ${c.page}` : 'No page'}
                                    {old ? ' · stored passage only' : ''}
                                  </span>
                                </div>
                              </div>
                              {!old ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  icon={<ExternalLink size={11} aria-hidden />}
                                  onClick={() => setViewing({ citation: c, label })}
                                >
                                  Highlight in doc
                                </Button>
                              ) : null}
                            </div>
                            <div className="prose prose-sm mt-2 max-h-36 max-w-none overflow-auto border-l-2 border-primary/50 pl-2.5 text-xs text-muted-foreground prose-p:my-1 prose-headings:my-1 prose-headings:text-foreground">
                              <SafeMarkdown text={c.snippet} />
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </CollapsiblePanel>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {children}
      {messageId && !streaming ? <FeedbackBar messageId={messageId} /> : null}
      <CitationViewerModal
        citation={viewing && canOpenViewer(viewing.citation) ? viewing.citation : null}
        label={viewing?.label}
        onClose={() => setViewing(null)}
      />
    </div>
  );
}
