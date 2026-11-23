'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, CheckCircle2, FileText, Loader2, UploadCloud } from 'lucide-react';
import { Button, Input, Modal } from '@/components/ui';
import { formatBytes } from '@/lib/chat/labels';
import {
  clearFinishedUploads,
  deleteUploaded,
  removeUpload,
  replaceUpload,
  retryProcessing,
  retryUpload,
  selectFiles,
} from '@/lib/upload/controller';
import type { UploadItem } from '@/lib/upload/queue';
import { batchSize, countItems, MAX_FILES_PER_BATCH } from '@/lib/upload/queue';
import { uploadScopes } from '@/lib/admin/documentsLayout';
import { useMyMember, usePublishers } from '@/lib/query/hooks';
import { useUploadStore } from '@/store/upload-store';

const ACCEPT = '.pdf,.md,.markdown,application/pdf,text/markdown';

const STATUS_LABEL: Record<UploadItem['status'], string> = {
  queued: 'Waiting',
  uploading: 'Uploading',
  processing: 'Processing',
  ready: 'Ready',
  failed: 'Failed',
};

function StatusMark({ status }: { status: UploadItem['status'] }) {
  const base = 'inline-flex items-center gap-1 text-xs font-medium';
  switch (status) {
    case 'ready':
      return <span className={`${base} text-success-foreground`}><CheckCircle2 size={14} aria-hidden />{STATUS_LABEL[status]}</span>;
    case 'failed':
      return <span className={`${base} text-danger-foreground`}><AlertCircle size={14} aria-hidden />{STATUS_LABEL[status]}</span>;
    case 'uploading':
    case 'processing':
      return <span className={`${base} text-info-foreground`}><Loader2 size={14} className="animate-spin" aria-hidden />{STATUS_LABEL[status]}</span>;
    default:
      return <span className={`${base} text-muted-foreground`}>{STATUS_LABEL[status]}</span>;
  }
}

function UploadRow({ item }: { item: UploadItem }) {
  const replaceInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const failure = item.failure;
  const stored = item.documentId !== null;
  // The document exists, so it can be deleted whatever the last failure was, unless nothing can be done (duplicate, unchanged).
  const deletable = stored && (item.stage === 'processing' || failure?.action !== 'none');

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  async function confirmedDelete() {
    setDeleteError(null);
    await run(async () => {
      const result = await deleteUploaded(item.id);
      if (result) setDeleteError(result.message);
    });
    setConfirmDelete(false);
  }

  const retryLabel = failure?.action === 'resend' ? 'Resend' : 'Retry';

  return (
    <li className="rounded-md border border-border bg-card p-3">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="flex min-w-0 items-start gap-2">
          <FileText size={16} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0">
            <p className="break-words text-sm font-medium">{item.file.name}</p>
            <p className="text-xs text-muted-foreground">{formatBytes(item.file.size)}</p>
          </div>
        </div>
        <StatusMark status={item.status} />
      </div>

      {failure ? (
        <p role="alert" className="mt-2 text-sm text-danger-foreground">
          {failure.message}
          {failure.existing ? (
            <>
              {' '}
              <Link
                href={`/documents/${encodeURIComponent(failure.existing.documentId)}`}
                className="underline"
                onClick={() => useUploadStore.getState().setDialogOpen(false)}
              >
                Open document
              </Link>
            </>
          ) : null}
          {failure.traceId ? <span className="block text-xs text-muted-foreground">Trace: {failure.traceId}</span> : null}
        </p>
      ) : null}
      {deleteError ? <p role="alert" className="mt-1 text-sm text-danger-foreground">{deleteError}</p> : null}

      {item.status === 'processing' ? (
        <p className="mt-1 text-xs text-muted-foreground">You can close this window; processing continues.</p>
      ) : null}

      <div className="mt-2 flex flex-wrap gap-2">
        {item.status === 'failed' && failure && !confirmDelete ? (
          <>
            {failure.action === 'retry' || failure.action === 'resend' ? (
              <Button
                size="sm"
                variant="outline"
                loading={busy}
                onClick={() => (item.stage === 'processing' ? void run(() => retryProcessing(item.id)) : retryUpload(item.id))}
              >
                {retryLabel}
              </Button>
            ) : null}
            {failure.action === 'replace' || deletable ? (
              <>
                <Button size="sm" variant="outline" disabled={busy} onClick={() => replaceInput.current?.click()}>
                  Replace file
                </Button>
                <input
                  ref={replaceInput}
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  tabIndex={-1}
                  aria-label={`Replacement for ${item.file.name}`}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = '';
                    if (file) replaceUpload(item.id, file);
                  }}
                />
              </>
            ) : null}
            {deletable ? (
              <Button size="sm" variant="dangerOutline" disabled={busy} onClick={() => setConfirmDelete(true)}>
                Delete
              </Button>
            ) : (
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => removeUpload(item.id)}>
                {stored ? 'Dismiss' : 'Remove'}
              </Button>
            )}
          </>
        ) : null}
        {confirmDelete ? (
          <>
            <span className="self-center text-sm">Delete this document from the workspace?</span>
            <Button size="sm" variant="destructive" loading={busy} onClick={() => void confirmedDelete()}>
              Delete document
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
          </>
        ) : null}
        {item.status === 'queued' ? (
          <Button size="sm" variant="ghost" onClick={() => removeUpload(item.id)}>
            Remove
          </Button>
        ) : null}
      </div>
    </li>
  );
}

/** The dialog is only a view of the shared queue: closing it never stops an upload. */
export function UploadDialog() {
  const open = useUploadStore((s) => s.dialogOpen);
  const setOpen = useUploadStore((s) => s.setDialogOpen);
  const queue = useUploadStore((s) => s.queue);
  const notice = useUploadStore((s) => s.notice);
  const picker = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const me = useMyMember();
  const publishers = usePublishers();
  const choices = uploadScopes(me.data?.publisherOf);
  const [scopeKey, setScopeKey] = useState('');
  const [preparedBy, setPreparedBy] = useState('');
  const choice = choices.find((c) => c.key === scopeKey) ?? choices[0];
  const departmentName = (id: string) => publishers.data?.departments.find((d) => d.departmentId === id)?.name ?? 'your department';
  const choiceLabel = (c: (typeof choices)[number]) =>
    c.scope.kind === 'WORKSPACE' ? 'Whole workspace (everyone can read)' : `${departmentName(c.scope.departmentId)} only (its members can read)`;
  const addFilesToScope = (files: File[]) => {
    if (choice) selectFiles(files, choice.scope, preparedBy.trim() === '' ? null : preparedBy.trim());
  };

  const counts = countItems(queue);
  const full = batchSize(queue) >= MAX_FILES_PER_BATCH;
  const hasFinished = counts.ready > 0 || queue.items.some((i) => i.status === 'failed' && i.failure?.action === 'none');
  const sending = counts.uploading + counts.queued;

  return (
    <Modal
      open={open}
      onClose={() => setOpen(false)}
      title="Upload documents"
      description={`PDF with a text layer or Markdown, up to 20 MB each, ${MAX_FILES_PER_BATCH} files per batch.`}
      size="lg"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            {sending > 0 ? 'Keep this tab open while files are being sent. You can close this window.' : 'Closing this window never cancels an upload.'}
          </p>
          <div className="flex gap-2">
            {hasFinished ? (
              <Button size="sm" variant="ghost" onClick={clearFinishedUploads}>
                Clear finished
              </Button>
            ) : null}
            <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {choices.length === 0 ? (
          <p role="alert" className="text-sm text-warning-foreground">
            You are not a publisher here. Ask an owner to make you the publisher of your department or the workspace.
          </p>
        ) : (
          <fieldset className="space-y-1 border-0 p-0">
            <legend className="mb-1 text-sm font-medium">Who can read these documents</legend>
            {choices.length === 1 ? (
              <p className="text-sm">{choiceLabel(choices[0])}</p>
            ) : (
              <div role="radiogroup" aria-label="Who can read these documents" className="space-y-1 text-sm">
                {choices.map((c) => (
                  <label key={c.key} className="flex items-center gap-2">
                    <input type="radio" name="upload-scope" checked={choice?.key === c.key} onChange={() => setScopeKey(c.key)} />
                    {choiceLabel(c)}
                  </label>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Only an owner can change this after upload. It applies to files you add from now on.
            </p>
          </fieldset>
        )}
        {choice ? (
          <Input
            label="Prepared by (optional)"
            maxLength={100}
            value={preparedBy}
            onChange={(e) => setPreparedBy(e.target.value)}
            placeholder={choice.scope.kind === 'DEPARTMENT' ? departmentName(choice.scope.departmentId) : 'For example: HR department'}
            helperText={
              choice.scope.kind === 'DEPARTMENT'
                ? 'Who drafted these documents. Left empty, it is your department.'
                : 'Who drafted these documents, so readers know where they come from. Applies to files you add from now on.'
            }
          />
        ) : null}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFilesToScope(Array.from(e.dataTransfer.files));
          }}
          className={`flex flex-col items-center gap-2 rounded-lg border-2 border-dashed text-center text-sm ${choice ? '' : 'pointer-events-none opacity-50 '}${
            full ? 'p-3' : 'p-5'
          } ${dragging ? 'border-primary bg-primary-soft' : 'border-input bg-muted'}`}
        >
          {full ? null : (
            <>
              <UploadCloud size={24} className="text-primary" aria-hidden />
              <p>Drop files here, or</p>
              <Button variant="primary" size="sm" onClick={() => picker.current?.click()}>
                Choose files
              </Button>
            </>
          )}
          <input
            ref={picker}
            type="file"
            multiple
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-label="Files to upload"
            onChange={(e) => {
              addFilesToScope(Array.from(e.target.files ?? []));
              e.target.value = '';
            }}
          />
          {full ? <p className="text-xs text-muted-foreground">The batch is full. Clear finished files to add more.</p> : null}
        </div>

        {notice ? <p role="status" className="text-sm text-warning-foreground">{notice}</p> : null}

        {queue.items.length > 0 ? (
          <>
            <p role="status" className="text-sm text-muted-foreground">
              {sending > 0 ? `Sending ${counts.uploading} now, ${counts.queued} waiting. ` : ''}
              {counts.processing > 0 ? `${counts.processing} processing. ` : ''}
              {counts.ready > 0 ? `${counts.ready} ready. ` : ''}
              {counts.failed > 0 ? `${counts.failed} need attention.` : ''}
            </p>
            <ul className="flex flex-col gap-2" aria-label="Files">
              {queue.items.map((item) => (
                <UploadRow key={item.id} item={item} />
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </Modal>
  );
}
