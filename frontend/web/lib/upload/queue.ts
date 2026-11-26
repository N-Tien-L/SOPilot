// The upload queue as pure state transitions (V2-31, frontend-nfrs R2). No React, no fetch, no
// timers: the manager in components/documents/UploadManager.tsx drives it and tests cover it.
//
// One file = one item = one independent request. A failed item never changes another item, and
// retrying only ever touches the item it was asked about.

import { classifyProcessingFailure, type UploadFailure } from './failure';
import { checkFile, type FileRef } from './validate';

export const MAX_FILES_PER_BATCH = 10;
export const MAX_CONCURRENT_UPLOADS = 3;

export type UploadStatus = 'queued' | 'uploading' | 'processing' | 'ready' | 'failed';

export type UploadKind = 'new_document' | 'new_version';

/** Where a failed item failed: before it was stored (`upload`) or while processing a stored document. */
export type FailureStage = 'client' | 'upload' | 'processing';

/**
 * Where a new document is published (ADR-009): the whole workspace (the workspace publisher), or one
 * department that the uploader publishes for (that department's publisher). It cannot be changed later
 * except by an owner, so it is chosen before the file is sent and kept for retries.
 */
export type UploadScope = { kind: 'WORKSPACE' } | { kind: 'DEPARTMENT'; departmentId: string };

export const WORKSPACE_SCOPE: UploadScope = { kind: 'WORKSPACE' };

/** Existing document chosen for a new-version upload. */
export interface VersionTarget {
  documentId: string;
  title: string;
  currentVersionNo: number;
}

export interface UploadItem {
  id: string;
  kind: UploadKind;
  scope: UploadScope;
  /** Who drafted the content, typed once for the batch; empty lets core-api default it (a department document gets its department). */
  preparedBy: string | null;
  file: FileRef;
  status: UploadStatus;
  failure: UploadFailure | null;
  stage: FailureStage | null;
  /** Set once the document exists; later uploads of the same item become new versions of it. */
  documentId: string | null;
  /** Only set when `kind === 'new_version'`: display info for the document being updated. */
  targetTitle: string | null;
  targetVersionNo: number | null;
}

export interface UploadQueue {
  items: readonly UploadItem[];
}

/** Failure code of a document whose status could not be read; its Retry only resumes polling. */
export const STATUS_UNKNOWN = 'STATUS_UNKNOWN';

export const emptyQueue: UploadQueue = { items: [] };

function update(queue: UploadQueue, id: string, change: (item: UploadItem) => UploadItem): UploadQueue {
  let changed = false;
  const items = queue.items.map((item) => {
    if (item.id !== id) return item;
    const next = change(item);
    if (next !== item) changed = true;
    return next;
  });
  return changed ? { items } : queue;
}

function failed(item: UploadItem, stage: FailureStage, failure: UploadFailure): UploadItem {
  return { ...item, status: 'failed', stage, failure };
}

/**
 * Items that occupy a batch slot: files waiting, being sent or needing attention. Once the bytes are
 * sent (processing, ready) the file no longer blocks the next batch (FR-30: users are not made to wait).
 */
export function batchSize(queue: UploadQueue): number {
  return queue.items.filter((i) => i.status !== 'processing' && i.status !== 'ready').length;
}

export interface AddResult {
  queue: UploadQueue;
  /** Files dropped because the batch is full (FR-30: 10 per batch). */
  notAdded: number;
}

/**
 * Adds files up to the batch limit. A file that fails the client check still takes a slot and is
 * listed as failed with its own reason, so the user sees which file was refused and why.
 */
export function addFiles(
  queue: UploadQueue,
  candidates: readonly { id: string; file: FileRef }[],
  scope: UploadScope = WORKSPACE_SCOPE,
  preparedBy: string | null = null,
): AddResult {
  const room = Math.max(0, MAX_FILES_PER_BATCH - batchSize(queue));
  const accepted = candidates.slice(0, room);
  const added: UploadItem[] = accepted.map(({ id, file }) => {
    const problem = checkFile(file);
    const base: UploadItem = {
      id,
      kind: 'new_document',
      scope,
      preparedBy,
      file,
      status: 'queued',
      failure: null,
      stage: null,
      documentId: null,
      targetTitle: null,
      targetVersionNo: null,
    };
    if (!problem) return base;
    return failed(base, 'client', { message: problem.message, action: 'replace', code: problem.code, traceId: null });
  });
  return { queue: { items: [...queue.items, ...added] }, notAdded: candidates.length - accepted.length };
}

export type AddVersionResult =
  | { queue: UploadQueue; added: true; reason: null }
  | { queue: UploadQueue; added: false; reason: 'batch_full' | 'already_in_queue' };

/** Document ids that currently have an active (queued, uploading, or processing) upload item. */
export function activeDocumentIds(queue: UploadQueue): Set<string> {
  const ids = new Set<string>();
  for (const item of queue.items) {
    if (
      item.documentId &&
      (item.status === 'queued' || item.status === 'uploading' || item.status === 'processing')
    ) {
      ids.add(item.documentId);
    }
  }
  return ids;
}

/**
 * Adds a single replacement file for an existing document as a new version. Refuses when the batch
 * is full or when the same document already has an active upload/processing item in the queue.
 */
export function addVersionFile(
  queue: UploadQueue,
  candidate: { id: string; file: FileRef },
  target: VersionTarget,
): AddVersionResult {
  if (activeDocumentIds(queue).has(target.documentId)) {
    return { queue, added: false, reason: 'already_in_queue' };
  }
  if (batchSize(queue) >= MAX_FILES_PER_BATCH) {
    return { queue, added: false, reason: 'batch_full' };
  }
  const problem = checkFile(candidate.file);
  const base: UploadItem = {
    id: candidate.id,
    kind: 'new_version',
    scope: WORKSPACE_SCOPE,
    preparedBy: null,
    file: candidate.file,
    status: 'queued',
    failure: null,
    stage: null,
    documentId: target.documentId,
    targetTitle: target.title,
    targetVersionNo: target.currentVersionNo,
  };
  const item = problem
    ? failed(base, 'client', { message: problem.message, action: 'replace', code: problem.code, traceId: null })
    : base;
  return { queue: { items: [...queue.items, item] }, added: true, reason: null };
}

/** Ids to start now: queued items, in order, while fewer than `limit` are uploading. */
export function startable(queue: UploadQueue, limit: number = MAX_CONCURRENT_UPLOADS): string[] {
  const uploading = queue.items.filter((i) => i.status === 'uploading').length;
  const free = Math.max(0, limit - uploading);
  return queue.items.filter((i) => i.status === 'queued').slice(0, free).map((i) => i.id);
}

export function markUploading(queue: UploadQueue, id: string): UploadQueue {
  return update(queue, id, (item) =>
    item.status === 'queued' ? { ...item, status: 'uploading', failure: null, stage: null } : item,
  );
}

/** The request succeeded. Only "processing" is shown until the document is READY (FR-30). */
export function markUploaded(queue: UploadQueue, id: string, documentId: string): UploadQueue {
  return update(queue, id, (item) =>
    item.status === 'uploading' ? { ...item, status: 'processing', documentId, failure: null, stage: null } : item,
  );
}

export function markUploadFailed(queue: UploadQueue, id: string, failure: UploadFailure): UploadQueue {
  return update(queue, id, (item) => (item.status === 'uploading' ? failed(item, 'upload', failure) : item));
}

export interface DocumentProgress {
  status: 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED';
  failureCode: string | null;
}

/** Polling result for a stored document: moves matching `processing` items to ready or failed. */
export function applyDocumentStatus(queue: UploadQueue, documentId: string, progress: DocumentProgress): UploadQueue {
  let changed = false;
  const items = queue.items.map((item) => {
    if (item.status !== 'processing' || item.documentId !== documentId) return item;
    if (progress.status === 'READY') {
      changed = true;
      return { ...item, status: 'ready' as const, failure: null, stage: null };
    }
    if (progress.status === 'FAILED') {
      changed = true;
      return failed(item, 'processing', classifyProcessingFailure(progress.failureCode));
    }
    return item;
  });
  return changed ? { items } : queue;
}

/**
 * The tracked document is gone (deleted elsewhere, or no longer readable): say so and stop tracking
 * it, so polling cannot go on for ever (R3).
 */
export function markDocumentGone(queue: UploadQueue, documentId: string): UploadQueue {
  let changed = false;
  const items = queue.items.map((item) => {
    if (item.status !== 'processing' || item.documentId !== documentId) return item;
    changed = true;
    return failed(item, 'processing', {
      message: 'This document was removed from the workspace.',
      action: 'none',
      code: 'NOT_FOUND',
      traceId: null,
    });
  });
  return changed ? { items } : queue;
}

/**
 * The status of a tracked document could not be read several times in a row (not a 404): stop polling
 * it and let the user ask again with Retry, so polling cannot go on for ever (R3).
 */
export function markStatusUnknown(queue: UploadQueue, documentId: string): UploadQueue {
  let changed = false;
  const items = queue.items.map((item) => {
    if (item.status !== 'processing' || item.documentId !== documentId) return item;
    changed = true;
    return failed(item, 'processing', {
      message: 'The status of this document could not be checked. Retry to check again.',
      action: 'retry',
      code: STATUS_UNKNOWN,
      traceId: null,
    });
  });
  return changed ? { items } : queue;
}

/** Retry or Resend of a file whose upload failed: back to the queue; nothing else changes. */
export function requeue(queue: UploadQueue, id: string): UploadQueue {
  return update(queue, id, (item) =>
    item.status === 'failed' && item.stage === 'upload' && item.failure?.action !== 'none'
      ? { ...item, status: 'queued', failure: null, stage: null }
      : item,
  );
}

/** Retry of a stored document that failed while processing: the API reprocesses it, no bytes are sent. */
export function restartProcessing(queue: UploadQueue, id: string): UploadQueue {
  return update(queue, id, (item) =>
    item.status === 'failed' && item.stage === 'processing' && item.documentId
      ? { ...item, status: 'processing', failure: null, stage: null }
      : item,
  );
}

/** A follow-up call on a failed item (retry, delete) failed too: show the new reason, keep the item failed. */
export function setFailure(queue: UploadQueue, id: string, failure: UploadFailure): UploadQueue {
  return update(queue, id, (item) => (item.status === 'failed' ? { ...item, failure } : item));
}

/** Replace file: a different file takes this item's place and goes back through the client check. */
export function replaceFile(queue: UploadQueue, id: string, file: FileRef): UploadQueue {
  return update(queue, id, (item) => {
    if (item.status !== 'failed') return item;
    const problem = checkFile(file);
    const next: UploadItem = { ...item, file, status: 'queued', failure: null, stage: null };
    if (!problem) return next;
    return failed(next, 'client', { message: problem.message, action: 'replace', code: problem.code, traceId: null });
  });
}

/** Removes an item that is not being sent right now. */
export function removeItem(queue: UploadQueue, id: string): UploadQueue {
  return { items: queue.items.filter((i) => i.id !== id || i.status === 'uploading') };
}

/** Drops finished entries (ready, or failed with nothing left to do) to free batch slots. */
export function clearFinished(queue: UploadQueue): UploadQueue {
  return {
    items: queue.items.filter(
      (i) => !(i.status === 'ready' || (i.status === 'failed' && i.failure?.action === 'none')),
    ),
  };
}

export interface QueueCounts {
  queued: number;
  uploading: number;
  processing: number;
  ready: number;
  failed: number;
}

export function countItems(queue: UploadQueue): QueueCounts {
  const counts: QueueCounts = { queued: 0, uploading: 0, processing: 0, ready: 0, failed: 0 };
  for (const item of queue.items) counts[item.status] += 1;
  return counts;
}

/** True while bytes are being sent or are still waiting to be sent (the leave-page warning). */
export function hasPendingBytes(queue: UploadQueue): boolean {
  return queue.items.some((i) => i.status === 'uploading' || i.status === 'queued');
}

/** Document ids that need status polling; empty means polling must stop (R3). */
export function processingDocumentIds(queue: UploadQueue): string[] {
  const ids = new Set<string>();
  for (const item of queue.items) {
    if (item.status === 'processing' && item.documentId) ids.add(item.documentId);
  }
  return [...ids];
}
