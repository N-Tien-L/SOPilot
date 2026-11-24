'use client';

import { useEffect } from 'react';
import { Loader2, Upload } from 'lucide-react';
import { pollProcessing } from '@/lib/upload/controller';
import { countItems, hasPendingBytes, processingDocumentIds } from '@/lib/upload/queue';
import { useUploadStore } from '@/store/upload-store';
import { UploadDialog } from './UploadDialog';

export const POLL_INTERVAL_MS = 3000;

/**
 * Mounted once in the authenticated shell, so the upload batch lives as long as the page does and
 * closing the dialog never cancels anything. It owns three things:
 * - the leave-page warning, only while bytes are being sent or are waiting to be sent;
 * - status polling, only while some uploaded document is still processing (R3);
 * - a small button that reopens the dialog while a batch is running.
 */
export function UploadManager() {
  const queue = useUploadStore((s) => s.queue);
  const dialogOpen = useUploadStore((s) => s.dialogOpen);
  const setDialogOpen = useUploadStore((s) => s.setDialogOpen);

  const pendingBytes = hasPendingBytes(queue);
  // Restarts only when polling starts or stops, not on every change of the tracked set
  // (each round reads the current ids itself), so quick completions cannot starve the poll.
  const tracking = processingDocumentIds(queue).length > 0;

  useEffect(() => {
    if (!pendingBytes) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [pendingBytes]);

  useEffect(() => {
    if (!tracking) return;
    const controller = new AbortController();
    let timer: number | undefined;
    // The next round starts only after the previous one finished, so slow responses never overlap.
    const round = async () => {
      await pollProcessing(controller.signal).catch(() => undefined);
      if (!controller.signal.aborted) timer = window.setTimeout(() => void round(), POLL_INTERVAL_MS);
    };
    timer = window.setTimeout(() => void round(), POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [tracking]);

  const counts = countItems(queue);
  const active = counts.queued + counts.uploading + counts.processing;
  const finished = queue.items.length - active;

  return (
    <>
      <UploadDialog />
      {queue.items.length > 0 ? (
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          hidden={dialogOpen}
          className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-card-foreground shadow-md hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          {active > 0 ? (
            <Loader2 size={16} className="animate-spin text-primary" aria-hidden />
          ) : (
            <Upload size={16} className="text-primary" aria-hidden />
          )}
          {counts.uploading + counts.queued > 0
            ? `Uploading ${counts.uploading + counts.queued} of ${queue.items.length}`
            : counts.processing > 0
              ? `Processing ${counts.processing}`
              : `Uploads: ${finished} done${counts.failed > 0 ? `, ${counts.failed} need attention` : ''}`}
        </button>
      ) : null}
    </>
  );
}
