'use client';

import { describeError } from '@/lib/api/errors';

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
    <p role="alert" className={`text-sm text-danger-foreground ${className}`}>
      {message}
      {traceId ? <span className="block text-xs text-muted-foreground">Trace: {traceId}</span> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 text-xs font-medium underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring"
        >
          Try again
        </button>
      ) : null}
    </p>
  );
}
