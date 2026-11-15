// Turns an API error, or a document that ended FAILED, into the sentence and the action the
// upload list shows (TECH-V2-core-api §5.5). Pure: tested without a network.

import { formatBytes } from '@/lib/chat/labels';

/**
 * - `retry`: send the same request again (transient error, or reprocess a stored document);
 * - `resend`: the network dropped, the same file can be sent again;
 * - `replace`: the content is the problem; pick another file or remove this one;
 * - `none`: nothing to retry (already stored, or not allowed); the user can only dismiss it.
 */
export type FailureAction = 'retry' | 'resend' | 'replace' | 'none';

export interface UploadFailure {
  message: string;
  action: FailureAction;
  code: string | null;
  traceId: string | null;
  /** DUPLICATE_DOCUMENT: the document that already has these bytes. */
  existing?: { documentId: string; title: string };
}

export interface ErrorLike {
  status: number;
  code: string | null;
  message: string;
  traceId: string | null;
  details: unknown;
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function quotaMessage(details: unknown): string {
  const d = record(details);
  const limit = typeof d.limit === 'number' ? d.limit : null;
  const used = typeof d.used === 'number' ? d.used : null;
  if (limit === null || used === null) return 'This workspace has reached its document limit.';
  if (d.kind === 'bytes') {
    return `This workspace is out of storage: ${formatBytes(used)} used of ${formatBytes(limit)}.`;
  }
  return `This workspace has reached its document limit: ${used} of ${limit} documents.`;
}

/** The failure of one upload request. `message` is the API's fixed sentence unless composed here. */
export function classifyUploadError(error: ErrorLike): UploadFailure {
  const base = { code: error.code, traceId: error.traceId };
  if (error.status === 0 || error.code === 'NETWORK_ERROR') {
    return { ...base, message: error.message, action: 'resend' };
  }
  switch (error.code) {
    case 'DUPLICATE_DOCUMENT': {
      const d = record(error.details);
      const documentId = typeof d.documentId === 'string' ? d.documentId : null;
      const title = typeof d.title === 'string' ? d.title : null;
      return {
        ...base,
        message: title ? `Already in the workspace as "${title}".` : 'Already in the workspace.',
        action: 'none',
        ...(documentId ? { existing: { documentId, title: title ?? 'the existing document' } } : {}),
      };
    }
    case 'DOCUMENT_UNCHANGED':
      return { ...base, message: 'The file content has not changed.', action: 'none' };
    case 'VERSION_IN_PROGRESS':
      return {
        ...base,
        message: 'A newer version of this document is still being processed. Try again when it is ready.',
        action: 'retry',
      };
    case 'QUOTA_EXCEEDED':
      return { ...base, message: quotaMessage(error.details), action: 'retry' };
    case 'NOT_PUBLISHER':
    case 'FORBIDDEN':
      return { ...base, message: 'You are not allowed to upload documents here.', action: 'none' };
  }
  if (error.status === 413) return { ...base, message: 'The file is larger than 20 MB.', action: 'replace' };
  if (error.status === 415 || error.status === 400) return { ...base, message: error.message, action: 'replace' };
  if (error.status === 403) return { ...base, message: 'You are not allowed to upload documents here.', action: 'none' };
  // 429, 5xx, anything unexpected: the same request may succeed later.
  return { ...base, message: error.message, action: 'retry' };
}

const PROCESSING_TEXT: Record<string, { message: string; action: FailureAction }> = {
  NO_TEXT_LAYER: { message: 'The PDF has no text layer (a scan). Upload a PDF with selectable text.', action: 'replace' },
  ENCRYPTED_PDF: { message: 'The PDF is encrypted or password protected. Upload an unlocked copy.', action: 'replace' },
  CORRUPT_FILE: { message: 'The file is damaged or cannot be read. Export it again and upload the new file.', action: 'replace' },
  UNSUPPORTED_TYPE: { message: 'This file type is not supported. Use a PDF with a text layer or a Markdown file.', action: 'replace' },
  INVALID_ENCODING: { message: 'The Markdown file is not UTF-8. Save it as UTF-8 and upload it again.', action: 'replace' },
  EMPTY_CONTENT: { message: 'No content could be extracted from the file.', action: 'replace' },
  EXTRACTION_ERROR: { message: 'Extracting the content failed. Try again.', action: 'retry' },
  EMBEDDING_ERROR: { message: 'The indexing service had a problem. Try again later.', action: 'retry' },
  OBJECT_NOT_FOUND: { message: 'The stored file could not be found. Try again.', action: 'retry' },
  RETRY_EXHAUSTED: { message: 'Processing failed after several attempts. Try again later.', action: 'retry' },
  DISPATCH_FAILED: { message: 'The document could not be handed to processing. Try again.', action: 'retry' },
};

/**
 * A stored document whose latest version ended FAILED. The text is local English by code: the
 * server stores a Vietnamese sentence in `failureMessage`, which the English UI does not show.
 */
export function classifyProcessingFailure(code: string | null): UploadFailure {
  const known = code ? PROCESSING_TEXT[code] : undefined;
  return {
    code,
    traceId: null,
    message: known?.message ?? 'Processing the document failed. Try again, or replace the file.',
    action: known?.action ?? 'retry',
  };
}
