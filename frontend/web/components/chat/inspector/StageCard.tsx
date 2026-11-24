'use client';

import { useId, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
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
import { cn } from '@/lib/utils';
import type { InspectorModalTarget } from './InspectorDetailModal';
import { StageDetails } from './StageDetails';

const STATUS_LABEL: Record<PipelineStepStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  passed: 'Passed',
  blocked: 'Blocked',
  skipped: 'Skipped',
  error: 'Error',
};

function StatusNode({ status, reduced }: { status: PipelineStepStatus; reduced: boolean }) {
  const base = 'relative z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full';

  let nodeClass = 'border border-border-strong bg-card text-muted-foreground/60';
  let icon = <Circle size={6} aria-hidden className="fill-current" />;

  switch (status) {
    case 'passed':
      nodeClass = 'bg-success-soft text-success-foreground';
      icon = <Check size={12} strokeWidth={2.5} aria-hidden />;
      break;
    case 'running':
      nodeClass = 'bg-primary-soft text-primary-strong';
      icon = <Loader2 size={12} aria-hidden className="animate-spin" />;
      break;
    case 'blocked':
      nodeClass = 'bg-warning-soft text-warning-foreground';
      icon = <ShieldAlert size={12} aria-hidden />;
      break;
    case 'error':
      nodeClass = 'bg-danger-soft text-danger-foreground';
      icon = <AlertCircle size={12} aria-hidden />;
      break;
    case 'skipped':
      nodeClass = 'border border-dashed border-border-strong bg-background text-muted-foreground';
      icon = <Minus size={11} aria-hidden />;
      break;
    default:
      break;
  }

  return (
    <span className="relative inline-flex h-5 w-5 shrink-0 items-center justify-center">
      {status === 'running' && !reduced ? (
        <motion.span
          aria-hidden
          className="absolute inset-0 rounded-full bg-primary/25"
          initial={{ scale: 0.9, opacity: 0.7 }}
          animate={{ scale: [1, 1.55, 1], opacity: [0.65, 0, 0.65] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
      ) : null}
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={status}
          initial={reduced ? { opacity: 0 } : { scale: 0.72, opacity: 0 }}
          animate={reduced ? { opacity: 1 } : { scale: 1, opacity: 1 }}
          exit={reduced ? { opacity: 0 } : { scale: 0.72, opacity: 0 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className={cn(base, nodeClass)}
        >
          {icon}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function StageCard({
  stage,
  trace,
  isLast,
  index = 0,
  onOpenModal,
}: {
  stage: AggregatedStage;
  trace: PipelineTrace;
  isLast: boolean;
  index?: number;
  onOpenModal: (target: InspectorModalTarget) => void;
}) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const reduced = useReducedMotion() ?? false;
  const panelId = useId();

  const hasDetails = stage.steps.length > 0 && stage.status !== 'pending';
  const autoOpen = stage.status === 'blocked' || stage.status === 'error';
  const open = hasDetails ? (manualOpen ?? autoOpen) : false;
  const muted = stage.status === 'pending' || stage.status === 'skipped';
  const finished = stage.status === 'passed' || stage.status === 'blocked' || stage.status === 'error';

  const summaryText = stage.summary || (stage.status === 'pending' ? null : stage.def.subtitle);

  const head = (
    <>
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            'block text-[13px] font-medium leading-5 transition-colors duration-150',
            muted ? 'text-muted-foreground' : 'text-foreground',
          )}
        >
          {stage.def.title}
        </span>
        {summaryText ? (
          <span
            className={cn(
              'block text-[13px] leading-5 [overflow-wrap:anywhere]',
              stage.status === 'blocked'
                ? 'text-warning-foreground'
                : stage.status === 'error'
                  ? 'text-danger-foreground'
                  : 'text-muted-foreground',
            )}
          >
            {stage.status === 'running' ? <ShinyText active>{summaryText}</ShinyText> : summaryText}
          </span>
        ) : null}
        <span className="sr-only">, {STATUS_LABEL[stage.status]}</span>
      </span>
      <span className="shrink-0 pt-px font-mono text-xs leading-5 tabular-nums text-muted-foreground">
        {stage.durationMs !== null && (finished || stage.status === 'running') ? formatMs(stage.durationMs) : ''}
      </span>
    </>
  );

  return (
    <motion.li
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 6 }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={{
        duration: 0.22,
        delay: reduced ? 0 : Math.min(index, 8) * 0.025,
        ease: [0.22, 1, 0.36, 1],
      }}
      className="relative flex gap-3 pb-3.5 last:pb-0"
    >
      {/* Vertical timeline rail with animated progress fill */}
      {!isLast ? (
        <span aria-hidden className="absolute bottom-0 left-[9.5px] top-6 w-px bg-border">
          <motion.span
            initial={false}
            animate={{ scaleY: stage.status === 'passed' ? 1 : stage.status === 'running' ? 0.45 : 0 }}
            transition={{ duration: reduced ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="block h-full w-full origin-top bg-primary/50"
          />
        </span>
      ) : null}

      <span className="pt-0.5">
        <StatusNode status={stage.status} reduced={reduced} />
      </span>

      <div className="min-w-0 flex-1">
        {hasDetails ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setManualOpen(!open)}
            className="-mx-2 -my-1 flex w-[calc(100%+16px)] cursor-pointer items-start gap-2 rounded-lg px-2 py-1 text-left transition-colors duration-150 hover:bg-muted/70 focus-visible:outline-2 focus-visible:outline-ring"
          >
            {head}
            <ChevronDown
              size={14}
              aria-hidden
              className={cn(
                'mt-[3px] shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none',
                open && 'rotate-180',
              )}
            />
          </button>
        ) : (
          <div className="flex items-start gap-2 pr-[22px]">{head}</div>
        )}

        {hasDetails ? (
          <CollapsiblePanel open={open} id={panelId}>
            <div className="mt-2 rounded-lg bg-muted/55 p-3">
              <StageDetails stage={stage} trace={trace} onOpenModal={onOpenModal} />
            </div>
          </CollapsiblePanel>
        ) : null}
      </div>
    </motion.li>
  );
}
