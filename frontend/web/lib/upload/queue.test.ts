import { describe, expect, it } from 'vitest';
import {
  activeDocumentIds,
  addFiles,
  addVersionFile,
  applyDocumentStatus,
  clearFinished,
  countItems,
  batchSize,
  markDocumentGone,
  markStatusUnknown,
  emptyQueue,
  hasPendingBytes,
  markUploadFailed,
  markUploaded,
  markUploading,
  MAX_CONCURRENT_UPLOADS,
  MAX_FILES_PER_BATCH,
  processingDocumentIds,
  removeItem,
  replaceFile,
  requeue,
  restartProcessing,
  setFailure,
  startable,
  type UploadQueue,
} from './queue';
import type { UploadFailure } from './failure';
import { MAX_FILE_BYTES } from './validate';

const pdf = (n: number, size = 1000) => ({ id: `f${n}`, file: { name: `sop-${n}.pdf`, size } });
const batch = (count: number) => Array.from({ length: count }, (_, i) => pdf(i + 1));
const transient: UploadFailure = { message: 'Try later.', action: 'retry', code: null, traceId: null };
const network: UploadFailure = { message: 'Offline.', action: 'resend', code: 'NETWORK_ERROR', traceId: null };

/** Starts everything `startable` allows, the way the manager does. */
function pump(queue: UploadQueue): UploadQueue {
  return startable(queue).reduce(markUploading, queue);
}

const statusOf = (queue: UploadQueue, id: string) => queue.items.find((i) => i.id === id)?.status;

describe('batch limit (FR-30)', () => {
  it('accepts 10 files', () => {
    const { queue, notAdded } = addFiles(emptyQueue, batch(10));
    expect(queue.items).toHaveLength(MAX_FILES_PER_BATCH);
    expect(notAdded).toBe(0);
  });

  it('blocks the 11th file and reports how many were dropped', () => {
    const { queue, notAdded } = addFiles(emptyQueue, batch(11));
    expect(queue.items).toHaveLength(10);
    expect(queue.items.some((i) => i.id === 'f11')).toBe(false);
    expect(notAdded).toBe(1);
  });

  it('counts files already in the list against the limit', () => {
    const first = addFiles(emptyQueue, batch(8)).queue;
    const second = addFiles(first, [pdf(9), pdf(10), pdf(11), pdf(12)]);
    expect(second.queue.items).toHaveLength(10);
    expect(second.notAdded).toBe(2);
  });

  it('frees slots when finished entries are cleared', () => {
    let q = addFiles(emptyQueue, batch(10)).queue;
    q = pump(q);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'READY', failureCode: null });
    q = clearFinished(q);
    expect(q.items).toHaveLength(9);
    expect(addFiles(q, [pdf(11)]).notAdded).toBe(0);
  });
});

describe('concurrency cap', () => {
  it('starts at most 3 of 10 files', () => {
    const q = addFiles(emptyQueue, batch(10)).queue;
    expect(startable(q)).toEqual(['f1', 'f2', 'f3']);
    const running = pump(q);
    expect(countItems(running)).toMatchObject({ uploading: MAX_CONCURRENT_UPLOADS, queued: 7 });
    expect(startable(running)).toEqual([]);
  });

  it('starts the next file as soon as one upload ends, success or failure', () => {
    let q = pump(addFiles(emptyQueue, batch(10)).queue);
    q = markUploaded(q, 'f1', 'd1');
    expect(startable(q)).toEqual(['f4']);
    q = pump(q);
    q = markUploadFailed(q, 'f2', transient);
    expect(startable(q)).toEqual(['f5']);
    q = pump(q);
    expect(countItems(q).uploading).toBe(3);
  });

  it('never has more than 3 uploading while a whole batch drains', () => {
    let q = addFiles(emptyQueue, batch(10)).queue;
    let peak = 0;
    for (let guard = 0; guard < 40 && countItems(q).queued + countItems(q).uploading > 0; guard += 1) {
      q = pump(q);
      peak = Math.max(peak, countItems(q).uploading);
      const next = q.items.find((i) => i.status === 'uploading');
      if (next) q = markUploaded(q, next.id, `d-${next.id}`);
    }
    expect(peak).toBe(3);
    expect(countItems(q).processing).toBe(10);
  });

  it('honours a different limit', () => {
    expect(startable(addFiles(emptyQueue, batch(5)).queue, 1)).toEqual(['f1']);
  });
});

describe('independent failure (FR-30)', () => {
  it('lets 8 files proceed when 2 fail on the client check', () => {
    const files = [
      ...batch(8),
      { id: 'scan', file: { name: 'notes.txt', size: 500 } },
      { id: 'big', file: { name: 'huge.pdf', size: MAX_FILE_BYTES + 1 } },
    ];
    let q = addFiles(emptyQueue, files).queue;
    expect(statusOf(q, 'scan')).toBe('failed');
    expect(statusOf(q, 'big')).toBe('failed');
    expect(q.items.find((i) => i.id === 'scan')?.failure?.message).toMatch(/\.md/);
    expect(countItems(q).queued).toBe(8);
    // failed files are never started
    expect(startable(q)).not.toContain('scan');
    q = pump(q);
    expect(countItems(q).uploading).toBe(3);
  });

  it('lets 8 files proceed when 2 uploads fail on the server', () => {
    let q = addFiles(emptyQueue, batch(10)).queue;
    const finished: string[] = [];
    for (let guard = 0; guard < 40 && countItems(q).queued + countItems(q).uploading > 0; guard += 1) {
      q = pump(q);
      const next = q.items.find((i) => i.status === 'uploading');
      if (!next) break;
      if (next.id === 'f3' || next.id === 'f7') {
        q = markUploadFailed(q, next.id, { ...transient, action: 'replace' });
      } else {
        q = markUploaded(q, next.id, `d-${next.id}`);
        finished.push(next.id);
      }
    }
    expect(countItems(q)).toMatchObject({ processing: 8, failed: 2 });
    expect(finished).toHaveLength(8);
  });

  it('a failure on one item leaves every other item untouched', () => {
    const q = pump(addFiles(emptyQueue, batch(3)).queue);
    const after = markUploadFailed(q, 'f2', transient);
    expect(after.items[0]).toBe(q.items[0]);
    expect(after.items[2]).toBe(q.items[2]);
  });
});

describe('retry', () => {
  it('requeues only the failed file; successful files are not sent again', () => {
    let q = pump(addFiles(emptyQueue, batch(3)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = markUploaded(q, 'f2', 'd2');
    q = markUploadFailed(q, 'f3', network);
    const retried = requeue(q, 'f3');
    expect(statusOf(retried, 'f3')).toBe('queued');
    expect(statusOf(retried, 'f1')).toBe('processing');
    expect(statusOf(retried, 'f2')).toBe('processing');
    expect(startable(retried)).toEqual(['f3']);
  });

  it('clears the failure when a failed file is requeued and when it starts again', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploadFailed(q, 'f1', transient);
    q = requeue(q, 'f1');
    expect(q.items[0].failure).toBeNull();
    q = markUploading(q, 'f1');
    expect(q.items[0].status).toBe('uploading');
  });

  it('does not requeue a file that is not retryable', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploadFailed(q, 'f1', { message: 'Already in the workspace.', action: 'none', code: 'DUPLICATE_DOCUMENT', traceId: null });
    expect(requeue(q, 'f1')).toBe(q);
  });

  it('does not requeue a client-side rejection', () => {
    const q = addFiles(emptyQueue, [{ id: 'x', file: { name: 'a.txt', size: 5 } }]).queue;
    expect(requeue(q, 'x')).toBe(q);
  });

  it('ignores a retry for a file that is not failed', () => {
    const q = pump(addFiles(emptyQueue, batch(1)).queue);
    expect(requeue(q, 'f1')).toBe(q);
  });

  it('reprocesses a stored document that failed in processing without sending bytes', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'FAILED', failureCode: 'EMBEDDING_ERROR' });
    expect(q.items[0]).toMatchObject({ status: 'failed', stage: 'processing' });
    expect(q.items[0].failure?.action).toBe('retry');
    q = restartProcessing(q, 'f1');
    expect(q.items[0].status).toBe('processing');
    expect(hasPendingBytes(q)).toBe(false);
  });

  it('keeps an item failed with the new reason when a follow-up call fails', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'FAILED', failureCode: 'EMBEDDING_ERROR' });
    q = setFailure(q, 'f1', { ...transient, message: 'Still failing.' });
    expect(q.items[0]).toMatchObject({ status: 'failed', stage: 'processing', failure: { message: 'Still failing.' } });
  });

  it('restartProcessing does nothing for an upload failure', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploadFailed(q, 'f1', transient);
    expect(restartProcessing(q, 'f1')).toBe(q);
  });
});

describe('batch slots (FR-30)', () => {
  it('a file whose bytes are sent no longer blocks the next batch', () => {
    let q = addFiles(emptyQueue, batch(10)).queue;
    for (let i = 0; i < 10; i += 1) {
      q = pump(q);
      const next = q.items.find((x) => x.status === 'uploading');
      if (next) q = markUploaded(q, next.id, `d-${next.id}`);
    }
    expect(countItems(q).processing).toBe(10);
    expect(batchSize(q)).toBe(0);
    const more = addFiles(q, [pdf(11), pdf(12)]);
    expect(more.notAdded).toBe(0);
    expect(more.queue.items).toHaveLength(12);
  });

  it('failed and waiting files still occupy a slot', () => {
    const q = addFiles(emptyQueue, [...batch(9), { id: 'bad', file: { name: 'x.txt', size: 3 } }]).queue;
    expect(batchSize(q)).toBe(10);
    expect(addFiles(q, [pdf(20)]).notAdded).toBe(1);
  });
});

describe('replace file', () => {
  it('keeps the document id (so Delete stays possible) when the replacement fails the client check', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'FAILED', failureCode: 'NO_TEXT_LAYER' });
    q = replaceFile(q, 'f1', { name: 'notes.docx', size: 9 });
    expect(q.items[0]).toMatchObject({ status: 'failed', stage: 'client', documentId: 'd1' });
  });

  it('requeue refuses a failure of the processing stage', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'FAILED', failureCode: 'EMBEDDING_ERROR' });
    expect(requeue(q, 'f1')).toBe(q);
  });

  it('puts a valid replacement back in the queue', () => {
    let q = addFiles(emptyQueue, [{ id: 'x', file: { name: 'a.txt', size: 5 } }]).queue;
    q = replaceFile(q, 'x', { name: 'a.md', size: 5 });
    expect(q.items[0]).toMatchObject({ status: 'queued', file: { name: 'a.md' }, failure: null });
  });

  it('keeps the item failed when the replacement is no better', () => {
    let q = addFiles(emptyQueue, [{ id: 'x', file: { name: 'a.txt', size: 5 } }]).queue;
    q = replaceFile(q, 'x', { name: 'b.docx', size: 5 });
    expect(q.items[0].status).toBe('failed');
    expect(q.items[0].failure?.message).toMatch(/PDF/);
  });

  it('only replaces a failed item', () => {
    const q = pump(addFiles(emptyQueue, batch(1)).queue);
    expect(replaceFile(q, 'f1', { name: 'z.pdf', size: 9 })).toBe(q);
  });

  it('keeps the document id so the replacement becomes a new version', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = applyDocumentStatus(q, 'd1', { status: 'FAILED', failureCode: 'NO_TEXT_LAYER' });
    q = replaceFile(q, 'f1', { name: 'text.pdf', size: 9 });
    expect(q.items[0]).toMatchObject({ status: 'queued', documentId: 'd1' });
  });
});

describe('processing tracking (R3)', () => {
  it('moves processing files to ready or failed by document id', () => {
    let q = pump(addFiles(emptyQueue, batch(3)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = markUploaded(q, 'f2', 'd2');
    q = markUploaded(q, 'f3', 'd3');
    q = applyDocumentStatus(q, 'd1', { status: 'READY', failureCode: null });
    q = applyDocumentStatus(q, 'd2', { status: 'FAILED', failureCode: 'NO_TEXT_LAYER' });
    q = applyDocumentStatus(q, 'd3', { status: 'PROCESSING', failureCode: null });
    expect(statusOf(q, 'f1')).toBe('ready');
    expect(statusOf(q, 'f2')).toBe('failed');
    expect(q.items[1].failure?.action).toBe('replace');
    expect(statusOf(q, 'f3')).toBe('processing');
  });

  it('lists document ids to poll and becomes empty when none are processing', () => {
    let q = pump(addFiles(emptyQueue, batch(2)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = markUploaded(q, 'f2', 'd2');
    expect(processingDocumentIds(q)).toEqual(['d1', 'd2']);
    q = applyDocumentStatus(q, 'd1', { status: 'READY', failureCode: null });
    q = applyDocumentStatus(q, 'd2', { status: 'FAILED', failureCode: null });
    expect(processingDocumentIds(q)).toEqual([]);
  });

  it('shows no content before READY: an uploaded file is only "processing"', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    expect(q.items[0].status).toBe('processing');
  });

  it('shows a document that no longer exists as failed and stops tracking it', () => {
    let q = pump(addFiles(emptyQueue, batch(2)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = markUploaded(q, 'f2', 'd2');
    q = markDocumentGone(q, 'd1');
    expect(processingDocumentIds(q)).toEqual(['d2']);
    expect(q.items[0]).toMatchObject({ status: 'failed', failure: { action: 'none', message: 'This document was removed from the workspace.' } });
  });

  it('turns a document whose status cannot be read into a retryable failure', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    q = markStatusUnknown(q, 'd1');
    expect(q.items[0]).toMatchObject({ status: 'failed', stage: 'processing', failure: { action: 'retry' } });
    expect(processingDocumentIds(q)).toEqual([]);
  });

  it('keeps the same queue object when a poll changes nothing', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploaded(q, 'f1', 'd1');
    expect(applyDocumentStatus(q, 'd1', { status: 'PROCESSING', failureCode: null })).toBe(q);
    expect(applyDocumentStatus(q, 'd1', { status: 'UPLOADED', failureCode: null })).toBe(q);
  });

  it('ignores a status for a document the queue is not tracking', () => {
    const q = pump(addFiles(emptyQueue, batch(1)).queue);
    expect(applyDocumentStatus(q, 'other', { status: 'READY', failureCode: null }).items[0]).toBe(q.items[0]);
  });
});

describe('leave-page warning', () => {
  it('is on while a file is uploading or waiting to be sent, and off afterwards', () => {
    let q = addFiles(emptyQueue, batch(4)).queue;
    expect(hasPendingBytes(q)).toBe(true);
    q = pump(q);
    for (const id of ['f1', 'f2', 'f3']) q = markUploaded(q, id, `d-${id}`);
    expect(hasPendingBytes(q)).toBe(true); // f4 is still queued
    q = pump(q);
    q = markUploaded(q, 'f4', 'd-f4');
    expect(hasPendingBytes(q)).toBe(false); // processing needs no open page
  });

  it('is off when only failed items remain', () => {
    let q = pump(addFiles(emptyQueue, batch(1)).queue);
    q = markUploadFailed(q, 'f1', transient);
    expect(hasPendingBytes(q)).toBe(false);
  });
});

describe('removeItem', () => {
  it('removes a failed or queued file but never one that is uploading', () => {
    let q = pump(addFiles(emptyQueue, batch(4)).queue);
    expect(removeItem(q, 'f1').items).toHaveLength(4);
    expect(removeItem(q, 'f4').items).toHaveLength(3);
    q = markUploadFailed(q, 'f1', transient);
    expect(removeItem(q, 'f1').items.some((i) => i.id === 'f1')).toBe(false);
  });
});

describe('new version uploads', () => {
  const target = { documentId: 'doc-42', title: 'Expense Policy', currentVersionNo: 2 };

  it('queues a new_version item with the existing document id and target metadata', () => {
    const res = addVersionFile(emptyQueue, { id: 'v1', file: { name: 'expense-v3.pdf', size: 2048 } }, target);
    expect(res.added).toBe(true);
    expect(res.queue.items[0]).toMatchObject({
      id: 'v1',
      kind: 'new_version',
      documentId: 'doc-42',
      targetTitle: 'Expense Policy',
      targetVersionNo: 2,
      status: 'queued',
    });
    expect(activeDocumentIds(res.queue).has('doc-42')).toBe(true);
  });

  it('refuses a second active version upload for the same document until the first finishes or fails', () => {
    const first = addVersionFile(emptyQueue, { id: 'v1', file: { name: 'a.pdf', size: 100 } }, target);
    const dup = addVersionFile(first.queue, { id: 'v2', file: { name: 'b.pdf', size: 100 } }, target);
    expect(dup).toMatchObject({ added: false, reason: 'already_in_queue' });

    const settled = applyDocumentStatus(markUploaded(pump(first.queue), 'v1', 'doc-42'), 'doc-42', {
      status: 'READY',
      failureCode: null,
    });
    expect(activeDocumentIds(settled).has('doc-42')).toBe(false);
    const next = addVersionFile(settled, { id: 'v3', file: { name: 'c.pdf', size: 100 } }, { ...target, currentVersionNo: 3 });
    expect(next.added).toBe(true);
  });

  it('refuses when the batch is full', () => {
    const full = addFiles(emptyQueue, batch(MAX_FILES_PER_BATCH)).queue;
    const res = addVersionFile(full, { id: 'v1', file: { name: 'a.pdf', size: 100 } }, target);
    expect(res).toMatchObject({ added: false, reason: 'batch_full' });
  });

  it('preserves new_version metadata when replacing a failed file', () => {
    const first = addVersionFile(emptyQueue, { id: 'v1', file: { name: 'bad.docx', size: 100 } }, target);
    expect(first.added).toBe(true);
    expect(first.queue.items[0]).toMatchObject({ status: 'failed', stage: 'client', kind: 'new_version', documentId: 'doc-42' });

    const replaced = replaceFile(first.queue, 'v1', { name: 'fixed.pdf', size: 500 });
    expect(replaced.items[0]).toMatchObject({
      status: 'queued',
      kind: 'new_version',
      documentId: 'doc-42',
      targetTitle: 'Expense Policy',
      targetVersionNo: 2,
      file: { name: 'fixed.pdf', size: 500 },
    });
  });
});
