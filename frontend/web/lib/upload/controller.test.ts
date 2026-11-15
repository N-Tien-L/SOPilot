import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api/errors';
import type { DocumentView } from '@/lib/api/types';
import { useSessionStore } from '@/store/session-store';
import { resetUploadState, useUploadStore } from '@/store/upload-store';

vi.mock('@/lib/api/endpoints', () => ({
  uploadDocument: vi.fn(),
  uploadDocumentVersion: vi.fn(),
  getDocument: vi.fn(),
  retryDocument: vi.fn(),
  deleteDocument: vi.fn(),
}));
vi.mock('@/lib/query/client', () => ({
  getQueryClient: () => ({ invalidateQueries: vi.fn() }),
  workspaceKey: (wid: string, ...parts: unknown[]) => ['ws', wid, ...parts],
}));

import * as api from '@/lib/api/endpoints';
import { MAX_POLL_ERRORS, pollProcessing, removeUpload, retryProcessing, retryUpload, selectFiles } from './controller';
import { confirmDiscardUploads } from './guard';
import { countItems, MAX_CONCURRENT_UPLOADS, processingDocumentIds } from './queue';

const upload = vi.mocked(api.uploadDocument);
const getDocument = vi.mocked(api.getDocument);
const retryDocument = vi.mocked(api.retryDocument);

interface Pending {
  file: File;
  signal: AbortSignal | undefined;
  resolve: (doc: DocumentView) => void;
  reject: (error: unknown) => void;
}
let pending: Pending[];

type DocStatus = 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED';
function doc(id: string, status: DocStatus = 'UPLOADED', failureCode: string | null = null): DocumentView {
  return {
    id,
    title: id,
    latestVersion: { id: `v-${id}`, versionNo: 1, status, failureCode, failureMessage: null },
  } as unknown as DocumentView;
}
const files = (n: number) => Array.from({ length: n }, (_, i) => new File([`content ${i}`], `f${i + 1}.md`));
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const counts = () => countItems(useUploadStore.getState().queue);
const signal = () => new AbortController().signal;
const workspace = (id: string) => ({ id, name: id, kind: 'TEAM', role: 'OWNER' as const });

beforeEach(() => {
  pending = [];
  vi.clearAllMocks();
  upload.mockImplementation(
    (file, abort) => new Promise<DocumentView>((resolve, reject) => pending.push({ file, signal: abort, resolve, reject })),
  );
  useSessionStore.setState({ workspace: workspace('w1') });
});
afterEach(() => resetUploadState());

async function oneProcessing() {
  selectFiles(files(1));
  pending[0].resolve(doc('d1'));
  await flush();
}

describe('controller: concurrency', () => {
  it('sends at most 3 requests and starts the next file when one finishes', async () => {
    selectFiles(files(10));
    expect(upload).toHaveBeenCalledTimes(MAX_CONCURRENT_UPLOADS);
    expect(counts()).toMatchObject({ uploading: 3, queued: 7 });
    pending[0].resolve(doc('d1'));
    await flush();
    expect(upload).toHaveBeenCalledTimes(4);
    expect(counts()).toMatchObject({ uploading: 3, queued: 6, processing: 1 });
  });

  it('keeps going when one upload fails and retries only that file', async () => {
    selectFiles(files(4));
    pending[0].reject(new ApiError(503, 'Unavailable.', 'STORAGE_UNAVAILABLE'));
    await flush();
    expect(counts()).toMatchObject({ failed: 1, uploading: 3 });
    const failedId = useUploadStore.getState().queue.items.find((i) => i.status === 'failed')!.id;
    pending[1].resolve(doc('d2'));
    await flush();
    const callsBefore = upload.mock.calls.length;
    retryUpload(failedId);
    expect(upload.mock.calls.length).toBe(callsBefore + 1);
    expect(upload.mock.calls.at(-1)![0].name).toBe('f1.md');
  });

  it('classifies a duplicate without retrying it', async () => {
    selectFiles(files(1));
    pending[0].reject(new ApiError(409, 'dup', 'DUPLICATE_DOCUMENT', null, { documentId: 'd9', title: 'Safety SOP' }));
    await flush();
    const item = useUploadStore.getState().queue.items[0];
    expect(item.failure).toMatchObject({ action: 'none', existing: { documentId: 'd9', title: 'Safety SOP' } });
  });
});

describe('controller: workspace reset (R7)', () => {
  it('aborts in-flight requests and forgets the batch', async () => {
    selectFiles(files(5));
    const signals = pending.map((p) => p.signal!);
    resetUploadState();
    expect(signals.every((s) => s.aborted)).toBe(true);
    expect(useUploadStore.getState().queue.items).toHaveLength(0);
    // aborted requests rejecting late must not touch the new state or start anything
    pending.forEach((p) => p.reject(new DOMException('aborted', 'AbortError')));
    await flush();
    expect(useUploadStore.getState().queue.items).toHaveLength(0);
    expect(upload).toHaveBeenCalledTimes(3);
  });

  it('ignores a response that arrives after the batch was reset', async () => {
    selectFiles(files(1));
    resetUploadState();
    pending[0].resolve(doc('late'));
    await flush();
    expect(useUploadStore.getState().queue.items).toHaveLength(0);
  });
});

describe('controller: polling (R3)', () => {
  it('moves a document to ready and then has nothing left to poll', async () => {
    await oneProcessing();
    getDocument.mockResolvedValue(doc('d1', 'PROCESSING'));
    await pollProcessing(signal());
    expect(processingDocumentIds(useUploadStore.getState().queue)).toEqual(['d1']);
    getDocument.mockResolvedValue(doc('d1', 'READY'));
    await pollProcessing(signal());
    expect(processingDocumentIds(useUploadStore.getState().queue)).toEqual([]);
    expect(counts().ready).toBe(1);
    getDocument.mockClear();
    await pollProcessing(signal());
    expect(getDocument).not.toHaveBeenCalled();
  });

  it('shows a processing failure by its code', async () => {
    await oneProcessing();
    getDocument.mockResolvedValue(doc('d1', 'FAILED', 'NO_TEXT_LAYER'));
    await pollProcessing(signal());
    expect(useUploadStore.getState().queue.items[0].failure?.message).toMatch(/no text layer/i);
  });

  it('shows a deleted document as removed', async () => {
    await oneProcessing();
    getDocument.mockRejectedValue(new ApiError(404, 'Not found.', 'NOT_FOUND'));
    await pollProcessing(signal());
    expect(useUploadStore.getState().queue.items[0].failure?.message).toMatch(/removed/);
  });

  it('gives up after repeated errors instead of polling for ever', async () => {
    await oneProcessing();
    getDocument.mockRejectedValue(new ApiError(503, 'Unavailable.', null));
    for (let i = 0; i < MAX_POLL_ERRORS - 1; i += 1) {
      await pollProcessing(signal());
      expect(counts().processing).toBe(1);
    }
    await pollProcessing(signal());
    expect(counts()).toMatchObject({ processing: 0, failed: 1 });
    expect(useUploadStore.getState().queue.items[0].failure?.action).toBe('retry');
  });

  it('a successful read resets the error count', async () => {
    await oneProcessing();
    getDocument.mockRejectedValue(new ApiError(503, 'x', null));
    for (let i = 0; i < MAX_POLL_ERRORS - 1; i += 1) await pollProcessing(signal());
    getDocument.mockResolvedValueOnce(doc('d1', 'PROCESSING'));
    await pollProcessing(signal());
    getDocument.mockRejectedValue(new ApiError(503, 'x', null));
    for (let i = 0; i < MAX_POLL_ERRORS - 1; i += 1) await pollProcessing(signal());
    expect(counts().processing).toBe(1);
  });

  it('drops results that belong to another workspace', async () => {
    await oneProcessing();
    getDocument.mockImplementation(async () => {
      useSessionStore.setState({ workspace: workspace('w2') });
      return doc('d1', 'READY');
    });
    await pollProcessing(signal());
    expect(counts().ready).toBe(0);
  });
});

describe('controller: retry of a stored document', () => {
  async function failedAfterUpload() {
    await oneProcessing();
    getDocument.mockResolvedValue(doc('d1', 'FAILED', 'EMBEDDING_ERROR'));
    await pollProcessing(signal());
    return useUploadStore.getState().queue.items[0].id;
  }

  it('treats VERSION_NOT_FAILED as "already moved on" and goes back to processing', async () => {
    const id = await failedAfterUpload();
    retryDocument.mockRejectedValue(new ApiError(409, 'not failed', 'VERSION_NOT_FAILED'));
    await retryProcessing(id);
    expect(useUploadStore.getState().queue.items[0].status).toBe('processing');
  });

  it('Retry after an unreadable status only resumes polling and never reprocesses', async () => {
    await oneProcessing();
    getDocument.mockRejectedValue(new ApiError(503, 'x', null));
    for (let i = 0; i < MAX_POLL_ERRORS; i += 1) await pollProcessing(signal());
    const id = useUploadStore.getState().queue.items[0].id;
    expect(useUploadStore.getState().queue.items[0].failure?.code).toBe('STATUS_UNKNOWN');
    await retryProcessing(id);
    expect(retryDocument).not.toHaveBeenCalled();
    expect(useUploadStore.getState().queue.items[0].status).toBe('processing');
  });

  it('keeps it failed, with the right verb, when retry is forbidden', async () => {
    const id = await failedAfterUpload();
    retryDocument.mockRejectedValue(new ApiError(403, 'no', 'NOT_PUBLISHER'));
    await retryProcessing(id);
    const item = useUploadStore.getState().queue.items[0];
    expect(item.status).toBe('failed');
    expect(item.failure?.message).toBe('You are not allowed to retry this document.');
  });
});

describe('guard: workspace switch and sign-out', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('does not ask when nothing is pending', () => {
    const confirm = vi.fn();
    vi.stubGlobal('window', { confirm });
    expect(confirmDiscardUploads()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });

  it('asks while files are uploading or waiting, and follows the answer', () => {
    selectFiles(files(5));
    const confirm = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.stubGlobal('window', { confirm });
    expect(confirmDiscardUploads()).toBe(false);
    expect(confirmDiscardUploads()).toBe(true);
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it('does not ask once every file has been sent', async () => {
    await oneProcessing();
    const confirm = vi.fn();
    vi.stubGlobal('window', { confirm });
    expect(confirmDiscardUploads()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });

  it('does not ask after the only file failed and was removed', async () => {
    selectFiles(files(1));
    pending[0].reject(new ApiError(500, 'x', null));
    await flush();
    removeUpload(useUploadStore.getState().queue.items[0].id);
    vi.stubGlobal('window', { confirm: vi.fn() });
    expect(confirmDiscardUploads()).toBe(true);
  });
});
