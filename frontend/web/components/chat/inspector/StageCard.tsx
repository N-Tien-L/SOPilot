'use client';

import { useState } from 'react';
import {
  AlertCircle,
  Check,
  ChevronDown,
  Circle,
  Loader2,
  Minus,
  ShieldAlert,
} from 'lucide-react';
import { ShinyText } from '@/components/effects';
import { CollapsiblePanel } from '@/components/motion/Primitives';
import type { PipelineStepStatus, PipelineTrace } from '@/lib/api/types';
import { formatMs, type AggregatedStage } from '@/lib/chat/pipeline-trace';
import type { InspectorModalTarget } from './InspectorDetailModal';
import { StageDetails } from './StageDetails';

const STATUS_STYLE: Record<
  PipelineStepStatus,
  { node: string; border: string; badge: string; label: string }
> = {
  pending: {
    node: 'border-border bg-card text-muted-foreground',
    border: 'border-border/70 bg-card/60',
    badge: 'bg-muted text-muted-foreground',
    label: 'Pending',
  },
  running: {
    node: 'border-primary bg-primary-soft text-primary-strong ring-4 ring-primary/15',
    border: 'border-primary/45 bg-card shadow-[var(--shadow-sm)]',
    badge: 'bg-primary-soft text-primary-strong',
    label: 'Running',
  },
  passed: {
    node: 'border-success/50 bg-success-soft text-success-foreground',
    border: 'border-border bg-card',
    badge: 'bg-success-soft text-success-foreground',
    label: 'Passed',
  },
  blocked: {
    node: 'border-warning bg-warning-soft text-warning-foreground ring-4 ring-warning/15',
    border: 'border-warning/60 border-l-4 border-l-warning bg-card shadow-[var(--shadow-sm)]',
    badge: 'bg-warning-soft text-warning-foreground',
    label: 'Blocked',
  },
  skipped: {
    node: 'border-dashed border-border bg-muted/50 text-muted-foreground',
    border: 'border-dashed border-border/60 bg-muted/25 opacity-70',
    badge: 'bg-muted text-muted-foreground',
    label: 'Skipped',
  },
  error: {
    node: 'border-danger bg-danger-soft text-danger-foreground ring-4 ring-danger/15',
    border: 'border-danger/60 border-l-4 border-l-danger bg-card shadow-[var(--shadow-sm)]',
    badge: 'bg-danger-soft text-danger-foreground',
    label: 'Error',
  },
};

function StatusIcon({ status }: { status: PipelineStepStatus }) {
  switch (status) {
    case 'running':
      return <Loader2 size={12} aria-hidden className="animate-spin" />;
    case 'passed':
      return <Check size={12} aria-hidden strokeWidth={2.5} />;
    case 'blocked':
      return <ShieldAlert size={12} aria-hidden />;
    case 'error':
      return <AlertCircle size={12} aria-hidden />;
    case 'skipped':
      return <Minus size={11} aria-hidden />;
    default:
      return <Circle size={9} aria-hidden />;
  }
}

const AUTO_EXPAND_STAGES = new Set(['retrieve_rerank', 'context_prompt', 'llm_generate']);

export function StageCard({
  stage,
  trace,
  isLast,
  onOpenModal,
}: {
  stage: AggregatedStage;
  trace: PipelineTrace;
  isLast: boolean;
  onOpenModal: (target: InspectorModalTarget) => void;
}) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const style = STATUS_STYLE[stage.status];
  const hasDetails = stage.steps.length > 0;
  const autoOpen =
    stage.status === 'running' ||
    stage.status === 'blocked' ||
    stage.status === 'error' ||
    (hasDetails && AUTO_EXPAND_STAGES.has(stage.def.id));
  const open = hasDetails ? (manualOpen ?? autoOpen) : false;

  return (
    <div className="relative flex gap-3 pb-3 last:pb-0">
      {/* Vertical timeline rail */}
      {!isLast ? (
        <span
          aria-hidden
          className={`absolute left-[11px] top-6 bottom-0 w-px ${
            stage.status === 'passed' ? 'bg-primary/35' : 'bg-border'
          }`}
        />
      ) : null}

      {/* Status node */}
      <div
        className={`relative z-10 mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-all ${style.node}`}
      >
        <StatusIcon status={stage.status} />
      </div>

      {/* Card body */}
      <div className={`min-w-0 flex-1 rounded-xl border transition-all ${style.border}`}>
        <button
          type="button"
          disabled={!hasDetails}
          aria-expanded={open}
          onClick={() => hasDetails && setManualOpen(!open)}
          className={`flex w-full items-start justify-between gap-2 px-3 py-2.5 text-left focus-visible:outline-2 focus-visible:outline-ring ${
            hasDetails ? 'cursor-pointer' : 'cursor-default'
          }`}
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[10px] font-bold text-muted-foreground">
                {String(stage.def.index).padStart(2, '0')}
              </span>
              <span className="truncate text-xs font-semibold text-foreground">{stage.def.title}</span>
            </div>
            {stage.summary ? (
              <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                {stage.status === 'running' ? <ShinyText active>{stage.summary}</ShinyText> : stage.summary}
              </p>
            ) : (
              <p className="mt-0.5 text-[11px] text-muted-foreground/70">{stage.def.subtitle}</p>
            )}
          </div>

          <div className="flex shrink-0 flex-col items-end gap-1">
            <div className="flex items-center gap-1">
              <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${style.badge}`}>
                {style.label}
              </span>
              {hasDetails ? (
                <ChevronDown
                  size={13}
                  aria-hidden
                  className={`text-muted-foreground transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
                />
              ) : null}
            </div>
            {stage.durationMs !== null ? (
              <span className="font-mono text-[10px] text-muted-foreground">{formatMs(stage.durationMs)}</span>
            ) : null}
          </div>
        </button>

        {hasDetails ? (
          <CollapsiblePanel open={open}>
            <div className="border-t border-border/60 px-3 py-2.5">
              <StageDetails stage={stage} trace={trace} onOpenModal={onOpenModal} />
            </div>
          </CollapsiblePanel>
        ) : null}
      </div>
    </div>
  );
}
