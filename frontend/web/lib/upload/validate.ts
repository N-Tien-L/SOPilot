// Client-side file check before any bytes are sent (V2-31, FR-06). Mirrors core-api's
// UploadValidator so the user hears about an unsupported or oversized file immediately; the
// server still re-checks everything. Next.js itself rejects bodies above 25 MB, so the size
// check here is also what keeps a 21-25 MB file from becoming an opaque 500.

export const MAX_FILE_BYTES = 20 * 1024 * 1024;

export interface FileRef {
  name: string;
  size: number;
}

export interface FileProblem {
  code: 'EMPTY_FILE' | 'FILE_TOO_LARGE' | 'UNSUPPORTED_TYPE';
  message: string;
}

const SUPPORTED = new Set(['pdf', 'md', 'markdown']);

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot < 0 ? '' : name.slice(dot + 1).trim().toLowerCase();
}

function unsupportedMessage(ext: string): string {
  switch (ext) {
    case 'txt':
      return 'Plain text (.txt) is not supported. Rename the file to .md and upload it again.';
    case 'doc':
    case 'docx':
      return 'Word files are not supported yet. Export the document to a PDF with a text layer.';
    default:
      return 'This file type is not supported. Upload a PDF with a text layer or a Markdown (.md) file.';
  }
}

/** Returns null when the file may be uploaded. */
export function checkFile(file: FileRef): FileProblem | null {
  if (file.size <= 0) return { code: 'EMPTY_FILE', message: 'The file is empty.' };
  const ext = extensionOf(file.name);
  if (!SUPPORTED.has(ext)) return { code: 'UNSUPPORTED_TYPE', message: unsupportedMessage(ext) };
  if (file.size > MAX_FILE_BYTES) {
    return { code: 'FILE_TOO_LARGE', message: 'The file is larger than 20 MB.' };
  }
  return null;
}
