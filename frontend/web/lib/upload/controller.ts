// Side effects of the upload queue (V2-31): starts requests, polls processing documents and keeps
// the TanStack Query cache fresh. The rules themselves are in queue.ts; this file only calls the API
// and feeds the results back. It runs outside React so closing the dialog cannot cancel an upload.

import {
  deleteDocument,
  getDocument,
  retryDocument,
  uploadDocument,
  uploadDocumentVersion,
} from '@/lib/api/endpoints';
import { isApiError } from '@/lib/api/errors';
import { getQueryClient, workspaceKey } from '@/lib/query/client';
import { useSessionStore } from '@/store/session-store';
import { fileFor, forgetFile, pollErrors, rememberFile, trackUpload, useUploadStore } from '@/store/upload-store';
import { classifyUploadError, type ErrorLike, type UploadFailure } from './failure';
import {
  addFiles,
  addVersionFile,
  applyDocumentStatus,
  clearFinished,
  markDocumentGone,
  markStatusUnknown,
  markUploaded,
  markUploadFailed,
  markUploading,
  MAX_FILES_PER_BATCH,
  processingDocumentIds,
  removeItem,
  replaceFile,
  requeue,
  restartProcessing,
  setFailure,
  startable,
  STATUS_UNKNOWN,
  WORKSPACE_SCOPE,
  type UploadScope,
  type VersionTarget,
} from './queue';

const store = () => useUploadStore.getState();
const currentWorkspaceId = (): string | null => useSessionStore.getState().workspace?.id ?? null;

function errorLike(error: unknown): ErrorLike {
  if (isApiError(error)) {
    return { status: error.status, code: error.code, message: error.message, traceId: error.traceId, details: error.details };
  }
  return { status: 500, code: null, message: 'Something went wrong. Please try again.', traceId: null, details: null };
}

/** Retry and delete are not uploads: a permission error must not say "upload". */
function followUpFailure(error: unknown, verb: 'retry' | 'delete'): UploadFailure {
  const failure = classifyUploadError(errorLike(error));
  if (failure.action === 'none' && (failure.code === 'NOT_PUBLISHER' || failure.code === 'FORBIDDEN' || (isApiError(error) && error.status === 403))) {
    return { ...failure, message: `You are not allowed to ${verb} this document.` };
  }
  return failure;
}

function refreshDocuments(workspaceId: string, documentId?: string): void {
  const client = getQueryClient();
  void client.invalidateQueries({ queryKey: workspaceKey(workspaceId, 'documents') });
  void client.invalidateQueries({ queryKey: workspaceKey(workspaceId, 'workspace') });
  if (documentId) {
    void client.invalidateQueries({ queryKey: workspaceKey(workspaceId, 'document', documentId) });
  } else {
    void client.invalidateQueries({ queryKey: workspaceKey(workspaceId, 'document') });
  }
}

/** Starts as many queued uploads as the concurrency cap allows. Safe to call at any time. */
function pump(): void {
  for (const id of startable(store().queue)) {
    store().update((q) => markUploading(q, id));
    void runUpload(id);
  }
}

async function runUpload(id: string): Promise<void> {
  const item = store().queue.items.find((i) => i.id === id);
  const file = fileFor(id);
  const workspaceId = currentWorkspaceId();
  if (!item || !file || !workspaceId) {
    store().update((q) =>
      markUploadFailed(q, id, { message: 'The file is no longer available. Add it again.', action: 'none', code: null, traceId: null }),
    );
    pump();
    return;
  }
  const controller = new AbortController();
  const untrack = trackUpload(id, controller);
  try {
    const document = item.documentId
      ? await uploadDocumentVersion(item.documentId, file, controller.signal)
      : await uploadDocument(file, item.scope, item.preparedBy, controller.signal);
    if (controller.signal.aborted) return;
    store().update((q) => markUploaded(q, id, document.id));
    refreshDocuments(workspaceId, document.id);
  } catch (error) {
    if (controller.signal.aborted) return;
    store().update((q) => markUploadFailed(q, id, classifyUploadError(errorLike(error))));
  } finally {
    untrack();
    if (!controller.signal.aborted) pump();
  }
}

/** Adds the chosen files (at most 10 per batch) to `scope`, with who prepared them, and starts uploading right away. */
export function selectFiles(
  selected: readonly File[],
  scope: UploadScope = WORKSPACE_SCOPE,
  preparedBy: string | null = null,
): void {
  if (selected.length === 0) return;
  const candidates = selected.map((file) => ({ id: crypto.randomUUID(), file }));
  const { queue, notAdded } = addFiles(
    store().queue,
    candidates.map(({ id, file }) => ({ id, file: { name: file.name, size: file.size } })),
    scope,
    preparedBy,
  );
  const kept = new Set(queue.items.map((i) => i.id));
  for (const { id, file } of candidates) {
    if (kept.has(id)) rememberFile(id, file);
  }
  store().update(() => queue);
  store().setNotice(
    notAdded > 0
      ? `A batch holds up to ${MAX_FILES_PER_BATCH} files. ${notAdded} ${notAdded === 1 ? 'file was' : 'files were'} not added.`
      : null,
  );
  pump();
}

/** Queues a new version file for an existing document and starts uploading right away. */
export function selectVersionFile(target: VersionTarget, file: File): boolean {
  const id = crypto.randomUUID();
  const result = addVersionFile(store().queue, { id, file: { name: file.name, size: file.size } }, target);
  if (!result.added) {
    store().setNotice(
      result.reason === 'already_in_queue'
        ? `A new version for "${target.title}" is already in the upload queue.`
        : `A batch holds up to ${MAX_FILES_PER_BATCH} files. Clear finished files to add more.`,
    );
    return false;
  }
  rememberFile(id, file);
  store().update(() => result.queue);
  store().setNotice(null);
  pump();
  return true;
}

/** Retry or Resend: sends the same file again; files that already succeeded are not touched. */
export function retryUpload(id: string): void {
  store().update((q) => requeue(q, id));
  pump();
}

/** Replace file: another file takes the item's place (a new version when the document already exists). */
export function replaceUpload(id: string, file: File): void {
  rememberFile(id, file);
  store().update((q) => replaceFile(q, id, { name: file.name, size: file.size }));
  pump();
}

export function removeUpload(id: string): void {
  forgetFile(id);
  store().update((q) => removeItem(q, id));
  pump();
}

export function clearFinishedUploads(): void {
  const before = store().queue.items;
  store().update((q) => clearFinished(q));
  const kept = new Set(store().queue.items.map((i) => i.id));
  for (const item of before) if (!kept.has(item.id)) forgetFile(item.id);
}

/** Retry for a stored document that failed while processing: no bytes are sent again. */
export async function retryProcessing(id: string): Promise<void> {
  const item = store().queue.items.find((i) => i.id === id);
  const workspaceId = currentWorkspaceId();
  if (!item?.documentId || !workspaceId) return;
  try {
    // A status that could not be read is only re-checked: reprocessing could redo a finished document.
    if (item.failure?.code !== STATUS_UNKNOWN) await retryDocument(item.documentId);
  } catch (error) {
    const failure = followUpFailure(error, 'retry');
    // VERSION_NOT_FAILED: it already moved on (another tab or a double click); polling will show where it is.
    if (!isApiError(error) || error.code !== 'VERSION_NOT_FAILED') {
      if (currentWorkspaceId() === workspaceId) store().update((q) => setFailure(q, id, failure));
      return;
    }
  }
  if (currentWorkspaceId() !== workspaceId) return;
  store().update((q) => restartProcessing(q, id));
  refreshDocuments(workspaceId);
}

/** Delete: removes the stored document. Resolves to a failure to show, or null when it is gone. */
export async function deleteUploaded(id: string): Promise<UploadFailure | null> {
  const item = store().queue.items.find((i) => i.id === id);
  const workspaceId = currentWorkspaceId();
  // Safety: never delete a pre-existing document from a failed new-version upload item.
  if (!item?.documentId || item.kind === 'new_version' || !workspaceId) return null;
  try {
    await deleteDocument(item.documentId);
  } catch (error) {
    if (!isApiError(error) || error.status !== 404) return followUpFailure(error, 'delete');
  }
  if (currentWorkspaceId() === workspaceId) {
    removeUpload(id);
    refreshDocuments(workspaceId);
  }
  return null;
}

export const MAX_POLL_ERRORS = 5;

/**
 * One polling round for every document still processing. The caller (the manager) schedules it only
 * while `processingDocumentIds` is not empty, so polling stops by itself (R3).
 */
export async function pollProcessing(signal: AbortSignal): Promise<void> {
  const workspaceId = currentWorkspaceId();
  const ids = processingDocumentIds(store().queue);
  if (!workspaceId || ids.length === 0) return;
  const results = await Promise.allSettled(ids.map((id) => getDocument(id, signal)));
  if (signal.aborted || currentWorkspaceId() !== workspaceId) return;
  let changed = false;
  results.forEach((result, index) => {
    const documentId = ids[index];
    if (result.status === 'fulfilled') {
      pollErrors.delete(documentId);
      const latest = result.value.latestVersion;
      if (latest.status === 'READY' || latest.status === 'FAILED') changed = true;
      store().update((q) => applyDocumentStatus(q, documentId, { status: latest.status, failureCode: latest.failureCode }));
    } else if (isApiError(result.reason) && result.reason.status === 404) {
      pollErrors.delete(documentId);
      store().update((q) => markDocumentGone(q, documentId));
      changed = true;
    } else {
      // Probably transient: ask again next round, but not for ever.
      const count = (pollErrors.get(documentId) ?? 0) + 1;
      if (count >= MAX_POLL_ERRORS) {
        pollErrors.delete(documentId);
        store().update((q) => markStatusUnknown(q, documentId));
      } else {
        pollErrors.set(documentId, count);
      }
    }
  });
  if (changed) refreshDocuments(workspaceId);
}
