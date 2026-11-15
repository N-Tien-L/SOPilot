'use client';

import { describeError } from '@/lib/api/errors';

/** Shows the API's fixed message and the trace id (S4, O2). */
export function ErrorNote({ error, className = '' }: { error: unknown; className?: string }) {
  const { message, traceId } = describeError(error);
  return (
    <p role="alert" className={`text-sm text-danger-foreground ${className}`}>
      {message}
      {traceId ? <span className="block text-xs text-muted-foreground">Trace: {traceId}</span> : null}
    </p>
  );
}
