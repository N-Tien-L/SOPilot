'use client';

import { useState } from 'react';
import {
  Activity,
  Code2,
  Lock,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import { Badge, Button, Skeleton } from '@/components/ui';
import type { PipelineTrace } from '@/lib/api/types';
import { aggregateStages, formatMs } from '@/lib/chat/pipeline-trace';
import { InspectorDetailModal, type InspectorModalTarget } from './InspectorDetailModal';
import { StageCard } from './StageCard';

export interface PipelineInspectorPanelProps {
  open: boolean;
  onToggle: () => void;
  trace: PipelineTrace | null;
  question: string | null;
  loading: boolean;
  error: boolean;
  onRetry?: () => void;
  isLive: boolean;
}

function outcomeBadge(trace: PipelineTrace): { variant: 'success' | 'warning' | 'danger' | 'info' | 'default'; label: string } {
  if (trace.live) return { variant: 'info', label: 'Live' };
  if (trace.hidden) return { variant: 'warning', label: 'Access Restricted' };
  if (trace.outcome === 'ANSWERED') return { variant: 'success', label: 'Answered' };
  if (trace.outcome === 'TEMPLATE') return { variant: 'info', label: 'Template' };
  if (trace.outcome === 'REFUSED_GUARD') return { variant: 'danger', label: 'Blocked · Guard' };
  if (trace.outcome === 'REFUSED_NO_EVIDENCE') {
    if (trace.refusalReason === 'OUT_OF_SCOPE') return { variant: 'warning', label: 'Out of Scope' };
    if (trace.refusalReason === 'GENERATOR_NOT_FOUND') return { variant: 'warning', label: 'Self-Refusal' };
    return { variant: 'warning', label: 'No Evidence' };
  }
  if (trace.outcome === 'QUOTA_EXCEEDED') return { variant: 'danger', label: 'Quota Exceeded' };
  if (trace.outcome === 'CANCELLED') return { variant: 'default', label: 'Stopped' };
  if (trace.outcome === 'ERROR') return { variant: 'danger', label: 'Error' };
  return { variant: 'default', label: 'Ready' };
}

export function PipelineInspectorPanel({
  open,
  onToggle,
  trace,
  question,
  loading,
  error,
  onRetry,
  isLive,
}: PipelineInspectorPanelProps) {
  const [modalTarget, setModalTarget] = useState<InspectorModalTarget | null>(null);
  const stages = trace ? aggregateStages(trace) : [];
  const badge = trace ? outcomeBadge(trace) : null;

  const panelBody = (
    <div className="flex h-full min-h-0 flex-col bg-card/85 backdrop-blur-sm">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">
            <Activity size={15} aria-hidden />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h2 className="truncate text-xs font-bold tracking-tight text-foreground">
                Pipeline Inspector
              </h2>
              {isLive ? (
                <span
                  aria-label="Live streaming"
                  className="inline-block h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse"
                />
              ) : null}
            </div>
            <p className="truncate text-[10px] text-muted-foreground">
              Query → Response real-time trace
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {trace && !trace.hidden ? (
            <button
              type="button"
              title="View raw JSON trace"
              aria-label="View raw JSON trace"
              onClick={() => setModalTarget({ kind: 'raw', trace })}
              className="cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            >
              <Code2 size={14} aria-hidden />
            </button>
          ) : null}
          <button
            type="button"
            onClick={onToggle}
            aria-label="Collapse Pipeline Inspector"
            title="Collapse Pipeline Inspector"
            className="hidden cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring lg:inline-flex"
          >
            <PanelRightClose size={15} aria-hidden />
          </button>
          <button
            type="button"
            onClick={onToggle}
            aria-label="Close Pipeline Inspector"
            className="inline-flex cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:hidden"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
      </div>

      {/* Turn summary bar */}
      {trace || question ? (
        <div className="shrink-0 space-y-2 border-b border-border/80 bg-muted/35 px-3.5 py-2.5">
          {question ? (
            <p className="line-clamp-2 text-xs font-medium text-foreground" title={question}>
              “{question}”
            </p>
          ) : null}
          {trace ? (
            <div className="flex flex-wrap items-center gap-1.5">
              {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
              <Badge variant="default" className="font-mono text-[10px]">
                {trace.mode}
              </Badge>
              <Badge variant="default" className="font-mono text-[10px]">
                {trace.lang.toUpperCase()}
              </Badge>
              {trace.totalMs != null ? (
                <span className="ml-auto font-mono text-[11px] font-semibold text-muted-foreground">
                  {formatMs(trace.totalMs)}
                </span>
              ) : null}
            </div>
          ) : null}
          {trace?.reconstructed ? (
            <p className="text-[10px] text-muted-foreground">
              Reconstructed from stored message log (prompt snapshot unavailable for legacy turns).
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Scrollable timeline body */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3.5">
        {loading && !trace ? (
          <div className="space-y-3">
            <Skeleton count={5} height={58} />
          </div>
        ) : error && !trace ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/40 p-4 text-center">
            <p className="text-xs font-medium text-foreground">Could not load pipeline trace.</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              The trace may belong to a deleted message or the server was unreachable.
            </p>
            {onRetry ? (
              <div className="mt-3">
                <Button size="sm" variant="outline" icon={<RotateCcw size={12} aria-hidden />} onClick={onRetry}>
                  Retry
                </Button>
              </div>
            ) : null}
          </div>
        ) : !trace ? (
          <div className="flex h-full min-h-[240px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/25 px-5 py-8 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary-strong">
              <Sparkles size={18} aria-hidden />
            </span>
            <h3 className="mt-3 text-sm font-semibold text-foreground">Ready to inspect</h3>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Send a question to watch all 11 RAG pipeline stages execute in real time, or select any previous turn.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {trace.hidden ? (
              <div className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning-soft px-3 py-2.5 text-xs text-warning-foreground">
                <Lock size={14} aria-hidden className="mt-0.5 shrink-0" />
                <span>
                  {trace.hiddenReason === 'DOCUMENT_DELETED'
                    ? 'Document-derived stages are hidden because a source document was deleted.'
                    : 'Document-derived stages are hidden because you no longer have access to a source document.'}
                </span>
              </div>
            ) : null}

            <div aria-label="Pipeline stages">
              {stages.map((stage, idx) => (
                <StageCard
                  key={`${trace.messageId ?? 'live'}:${stage.def.id}`}
                  stage={stage}
                  trace={trace}
                  isLast={idx === stages.length - 1}
                  onOpenModal={setModalTarget}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop docked collapsible side-panel */}
      <aside
        aria-label="Query Pipeline Inspector"
        className={`hidden shrink-0 border-l border-border transition-[width] duration-200 lg:flex lg:flex-col ${
          open ? 'w-[400px] xl:w-[440px]' : 'w-11'
        }`}
      >
        {open ? (
          panelBody
        ) : (
          <div className="flex h-full flex-col items-center bg-card/70 py-3">
            <button
              type="button"
              onClick={onToggle}
              aria-label="Expand Pipeline Inspector"
              title="Expand Pipeline Inspector"
              className="relative flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            >
              <PanelRightOpen size={16} aria-hidden />
              {isLive ? (
                <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse" />
              ) : null}
            </button>
            <span
              aria-hidden
              className="mt-4 select-none text-[10px] font-semibold uppercase tracking-widest text-muted-foreground [writing-mode:vertical-rl]"
            >
              Pipeline Inspector
            </span>
          </div>
        )}
      </aside>

      {/* Mobile / Tablet slide-over drawer */}
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close Pipeline Inspector"
            onClick={onToggle}
            className="absolute inset-0 bg-overlay backdrop-blur-xs"
          />
          <aside
            aria-label="Query Pipeline Inspector"
            className="absolute inset-y-0 right-0 flex w-[min(92vw,420px)] flex-col border-l border-border bg-card shadow-2xl"
          >
            {panelBody}
          </aside>
        </div>
      ) : null}

      <InspectorDetailModal target={modalTarget} onClose={() => setModalTarget(null)} />
    </>
  );
}
