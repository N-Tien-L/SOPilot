import { describe, expect, it } from 'vitest';
import { classifyProcessingFailure, classifyUploadError, type ErrorLike } from './failure';
import { checkFile, MAX_FILE_BYTES } from './validate';

const err = (status: number, code: string | null, details: unknown = null, message = 'Server sentence.'): ErrorLike => ({
  status,
  code,
  message,
  traceId: 'trace-1',
  details,
});

describe('classifyUploadError', () => {
  it('offers Resend on a network error', () => {
    expect(classifyUploadError(err(0, 'NETWORK_ERROR', null, 'Offline.'))).toMatchObject({ action: 'resend', message: 'Offline.' });
  });

  it('links to the existing document on DUPLICATE_DOCUMENT', () => {
    const f = classifyUploadError(err(409, 'DUPLICATE_DOCUMENT', { documentId: 'd9', title: 'Safety SOP', createdAt: 'x' }));
    expect(f.action).toBe('none');
    expect(f.existing).toEqual({ documentId: 'd9', title: 'Safety SOP' });
    expect(f.message).toContain('Safety SOP');
  });

  it('still reports a duplicate when the details are missing', () => {
    const f = classifyUploadError(err(409, 'DUPLICATE_DOCUMENT'));
    expect(f.message).toBe('Already in the workspace.');
    expect(f.existing).toBeUndefined();
  });

  it('says the content has not changed on DOCUMENT_UNCHANGED', () => {
    expect(classifyUploadError(err(409, 'DOCUMENT_UNCHANGED'))).toMatchObject({
      message: 'The file content has not changed.',
      action: 'none',
    });
  });

  it('allows a later retry on VERSION_IN_PROGRESS', () => {
    expect(classifyUploadError(err(409, 'VERSION_IN_PROGRESS')).action).toBe('retry');
  });

  it('shows the document quota and the amount used', () => {
    const f = classifyUploadError(err(409, 'QUOTA_EXCEEDED', { kind: 'documents', limit: 50, used: 50 }));
    expect(f.message).toBe('This workspace has reached its document limit: 50 of 50 documents.');
  });

  it('shows the storage quota in readable sizes', () => {
    const f = classifyUploadError(err(409, 'QUOTA_EXCEEDED', { kind: 'bytes', limit: 209715200, used: 209000000 }));
    expect(f.message).toContain('MB');
    expect(f.message).toContain('200.0 MB');
  });

  it('falls back to a plain quota sentence without details', () => {
    expect(classifyUploadError(err(409, 'QUOTA_EXCEEDED')).message).toMatch(/document limit/);
  });

  it('treats 413 as a content error', () => {
    expect(classifyUploadError(err(413, 'FILE_TOO_LARGE'))).toMatchObject({ action: 'replace', message: 'The file is larger than 20 MB.' });
  });

  it('keeps the API guidance for 415 and offers Replace', () => {
    const f = classifyUploadError(err(415, 'UNSUPPORTED_TYPE', null, 'Rename the file to .md.'));
    expect(f).toMatchObject({ action: 'replace', message: 'Rename the file to .md.' });
  });

  it('does not offer a retry when the user is not a publisher', () => {
    expect(classifyUploadError(err(403, 'NOT_PUBLISHER')).action).toBe('none');
  });

  it('offers Retry on 5xx and 429', () => {
    expect(classifyUploadError(err(503, 'STORAGE_UNAVAILABLE')).action).toBe('retry');
    expect(classifyUploadError(err(429, 'RATE_LIMITED')).action).toBe('retry');
  });

  it('carries the trace id', () => {
    expect(classifyUploadError(err(500, null)).traceId).toBe('trace-1');
  });
});

describe('classifyProcessingFailure', () => {
  it.each(['NO_TEXT_LAYER', 'ENCRYPTED_PDF', 'CORRUPT_FILE', 'INVALID_ENCODING', 'EMPTY_CONTENT', 'UNSUPPORTED_TYPE'])(
    '%s asks for a different file',
    (code) => expect(classifyProcessingFailure(code).action).toBe('replace'),
  );

  it.each(['EMBEDDING_ERROR', 'RETRY_EXHAUSTED', 'OBJECT_NOT_FOUND', 'EXTRACTION_ERROR'])('%s offers Retry', (code) =>
    expect(classifyProcessingFailure(code).action).toBe('retry'),
  );

  it('uses a generic retryable message for an unknown or missing code', () => {
    expect(classifyProcessingFailure('SOMETHING_NEW').action).toBe('retry');
    expect(classifyProcessingFailure(null).message).toMatch(/failed/);
  });
});

describe('checkFile', () => {
  it('accepts pdf, md and markdown in any case', () => {
    for (const name of ['a.pdf', 'A.PDF', 'notes.md', 'notes.MD', 'x.markdown']) {
      expect(checkFile({ name, size: 10 })).toBeNull();
    }
  });

  it('accepts exactly 20 MB and refuses one byte more', () => {
    expect(checkFile({ name: 'a.pdf', size: MAX_FILE_BYTES })).toBeNull();
    expect(checkFile({ name: 'a.pdf', size: MAX_FILE_BYTES + 1 })?.code).toBe('FILE_TOO_LARGE');
  });

  it('tells the user how to fix .txt and Word files', () => {
    expect(checkFile({ name: 'a.txt', size: 10 })?.message).toMatch(/\.md/);
    expect(checkFile({ name: 'a.docx', size: 10 })?.message).toMatch(/PDF with a text layer/);
  });

  it('refuses other types, files with no extension and empty files', () => {
    expect(checkFile({ name: 'a.png', size: 10 })?.code).toBe('UNSUPPORTED_TYPE');
    expect(checkFile({ name: 'README', size: 10 })?.code).toBe('UNSUPPORTED_TYPE');
    expect(checkFile({ name: 'a.pdf', size: 0 })?.code).toBe('EMPTY_FILE');
  });
});
