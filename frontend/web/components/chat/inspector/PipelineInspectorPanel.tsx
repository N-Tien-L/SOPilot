'use client';

import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import {
  Braces,
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
import { cn } from '@/lib/utils';
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

const EASE_OUT = [0.22, 1, 0.36, 1] as const;

function outcomeBadge(
  trace: PipelineTrace,
): { variant: 'success' | 'warning' | 'danger' | 'info' | 'default'; dot: string; label: string } {
  if (trace.live) return { variant: 'info', dot: 'bg-primary', label: 'Live' };
  if (trace.hidden) return { variant: 'warning', dot: 'bg-warning', label: 'Access restricted' };
  if (trace.outcome === 'ANSWERED') return { variant: 'success', dot: 'bg-success', label: 'Answered' };
  if (trace.outcome === 'TEMPLATE') return { variant: 'info', dot: 'bg-info', label: 'Template' };
  if (trace.outcome === 'REFUSED_GUARD') return { variant: 'danger', dot: 'bg-danger', label: 'Blocked · Guard' };
  if (trace.outcome === 'REFUSED_NO_EVIDENCE') {
    if (trace.refusalReason === 'OUT_OF_SCOPE') return { variant: 'warning', dot: 'bg-warning', label: 'Out of scope' };
    if (trace.refusalReason === 'GENERATOR_NOT_FOUND') return { variant: 'warning', dot: 'bg-warning', label: 'Self-refusal' };
    return { variant: 'warning', dot: 'bg-warning', label: 'No evidence' };
  }
  if (trace.outcome === 'QUOTA_EXCEEDED') return { variant: 'danger', dot: 'bg-danger', label: 'Quota exceeded' };
  if (trace.outcome === 'CANCELLED') return { variant: 'default', dot: 'bg-muted-foreground', label: 'Stopped' };
  if (trace.outcome === 'ERROR') return { variant: 'danger', dot: 'bg-danger', label: 'Error' };
  return { variant: 'default', dot: 'bg-muted-foreground', label: 'Ready' };
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
  const reduced = useReducedMotion() ?? false;
  const stages = trace ? aggregateStages(trace) : [];
  const badge = trace ? outcomeBadge(trace) : null;

  const panelBody = (
    <div className="flex h-full min-h-0 flex-col bg-card">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-5">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-[15px] font-semibold text-foreground">Pipeline</h2>
          {isLive ? (
            <span
              aria-label="Live streaming"
              className="inline-block h-2 w-2 rounded-full bg-primary motion-safe:animate-pulse"
            />
          ) : null}
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onToggle}
            aria-label="Collapse Pipeline Inspector"
            title="Collapse Pipeline Inspector"
            className="hidden cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring lg:inline-flex"
          >
            <PanelRightClose size={16} aria-hidden />
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

      {/* Scrollable body */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {loading && !trace ? (
          <div className="space-y-3">
            <Skeleton count={5} height={48} />
          </div>
        ) : error && !trace ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/40 p-4 text-center">
            <p className="text-sm font-medium text-foreground">Could not load pipeline trace.</p>
            <p className="mt-1 text-xs text-muted-foreground">
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
          <div className="py-6">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary-soft text-primary-strong">
              <Sparkles size={16} aria-hidden />
            </span>
            <h3 className="mt-3 text-sm font-semibold text-foreground">No question yet</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
              Send a question to watch all 11 stages run here: search, reranking, prompt assembly and citation checks.
            </p>
          </div>
        ) : (
          <motion.div
            key={trace.messageId ?? 'live'}
            initial={reduced ? { opacity: 0 } : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
          >
            {/* Question & badges summary */}
            {question ? (
              <p className="line-clamp-3 text-sm text-foreground [overflow-wrap:anywhere]" title={question}>
                “{question}”
              </p>
            ) : null}

            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {badge ? (
                <Badge variant={badge.variant} className="gap-1.5">
                  <span
                    aria-hidden
                    className={cn(
                      'inline-block h-1.5 w-1.5 rounded-full',
                      badge.dot,
                      isLive && 'motion-safe:animate-pulse',
                    )}
                  />
                  {badge.label}
                </Badge>
              ) : null}
              <Badge variant="default" className="font-mono text-xs">
                {trace.mode}
              </Badge>
              <Badge variant="default" className="font-mono text-xs">
                {trace.lang.toUpperCase()}
              </Badge>
              {trace.totalMs != null ? (
                <span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
                  {formatMs(trace.totalMs)}
                </span>
              ) : null}
            </div>

            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="truncate font-mono text-xs text-muted-foreground">
                {trace.messageId ? `Trace ${trace.messageId.slice(0, 12)}` : 'Live trace'}
              </p>
              {!trace.hidden ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="-mr-2 h-7 px-2 text-xs"
                  icon={<Braces size={13} aria-hidden />}
                  onClick={() => setModalTarget({ kind: 'raw', trace })}
                >
                  Raw trace
                </Button>
              ) : null}
            </div>

            {trace.reconstructed ? (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Reconstructed from stored message log (prompt snapshot unavailable for legacy turns).
              </p>
            ) : null}

            {trace.hidden ? (
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/35 bg-warning-soft px-3 py-2.5 text-xs text-warning-foreground">
                <Lock size={14} aria-hidden className="mt-0.5 shrink-0" />
                <span>
                  {trace.hiddenReason === 'DOCUMENT_DELETED'
                    ? 'Stages that used document text are hidden because a source document was deleted.'
                    : 'Stages that used document text are hidden because you no longer have access to a source document.'}
                </span>
              </div>
            ) : null}

            {/* Clean vertical stage timeline */}
            <ol aria-label="Pipeline stages" className="mt-4 border-t border-border pt-4">
              {stages.map((stage, idx) => (
                <StageCard
                  key={`${trace.messageId ?? 'live'}:${stage.def.id}`}
                  stage={stage}
                  trace={trace}
                  index={idx}
                  isLast={idx === stages.length - 1}
                  onOpenModal={setModalTarget}
                />
              ))}
            </ol>
          </motion.div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop docked collapsible side-panel with smooth width animation */}
      <motion.aside
        aria-label="Query Pipeline Inspector"
        initial={false}
        animate={{ width: open ? 408 : 44 }}
        transition={{ duration: reduced ? 0 : 0.24, ease: EASE_OUT }}
        className="hidden shrink-0 overflow-hidden border-l border-border lg:flex lg:flex-col"
      >
        <AnimatePresence mode="wait" initial={false}>
          {open ? (
            <motion.div
              key="expanded"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.16 }}
              className="flex h-full min-h-0 w-[408px] flex-col"
            >
              {panelBody}
            </motion.div>
          ) : (
            <motion.div
              key="collapsed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.16 }}
              className="flex h-full w-11 flex-col items-center bg-card py-3"
            >
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
                className="mt-4 select-none text-[11px] font-medium text-muted-foreground [writing-mode:vertical-rl]"
              >
                Pipeline
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.aside>

      {/* Mobile / Tablet animated slide-over drawer */}
      <AnimatePresence>
        {open ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.button
              type="button"
              aria-label="Close Pipeline Inspector"
              onClick={onToggle}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.2 }}
              className="absolute inset-0 bg-overlay backdrop-blur-xs"
            />
            <motion.aside
              aria-label="Query Pipeline Inspector"
              initial={reduced ? { opacity: 0 } : { x: '100%' }}
              animate={reduced ? { opacity: 1 } : { x: 0 }}
              exit={reduced ? { opacity: 0 } : { x: '100%' }}
              transition={{ duration: reduced ? 0.15 : 0.24, ease: EASE_OUT }}
              className="absolute inset-y-0 right-0 flex w-[min(92vw,420px)] flex-col border-l border-border bg-card shadow-2xl"
            >
              {panelBody}
            </motion.aside>
          </div>
        ) : null}
      </AnimatePresence>

      <InspectorDetailModal target={modalTarget} onClose={() => setModalTarget(null)} />
    </>
  );
}
