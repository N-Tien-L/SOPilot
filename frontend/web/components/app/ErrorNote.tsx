'use client';

import { AlertCircle } from 'lucide-react';
import { describeError } from '@/lib/api/errors';
import { cn } from '@/lib/utils';

/** Shows the API's fixed message and the trace id (S4, O2). */
export function ErrorNote({
  error,
  className = '',
  onRetry,
}: {
  error: unknown;
  className?: string;
  /** Shows a "Try again" button, for a list that can be reloaded. */
  onRetry?: () => void;
}) {
  const { message, traceId } = describeError(error);
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger-soft/75 px-3.5 py-2.5 text-sm text-danger-foreground',
        className,
      )}
    >
      <AlertCircle size={15} aria-hidden className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="leading-snug">{message}</p>
        {traceId ? <span className="mt-0.5 block font-mono text-[11px] opacity-80">Trace: {traceId}</span> : null}
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-1.5 cursor-pointer text-xs font-semibold underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring"
          >
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
