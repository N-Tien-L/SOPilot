// Fixed English copy for the recognized-content view (S4: never a raw code).

import type { ContentWarning, DocumentView } from '@/lib/api/types';

/** FR-31: said once, as a fixed sentence. There is no editor and no "checked" action. */
export const READY_MEANING =
  'READY means processing finished, not that the content has been checked. Compare it with the original before relying on it.';

/**
 * "Version N is used for Q&A; version N+1 is processing / failed" when the latest version differs
 * from the current one; null when they are the same (or there is no current version).
 */
export function versionNotice(doc: Pick<DocumentView, 'currentVersion' | 'latestVersion'>): string | null {
  const current = doc.currentVersion;
  const latest = doc.latestVersion;
  if (!current || current.id === latest.id) return null;
  const state = latest.status === 'FAILED' ? 'failed to process' : 'is processing';
  return `Version ${current.versionNo} is used for Q&A; version ${latest.versionNo} ${state}.`;
}

function pagesText(pages: number[] | undefined): string {
  if (!pages || pages.length === 0) return '';
  return pages.length === 1 ? ` (page ${pages[0]})` : ` (pages ${pages.join(', ')})`;
}

/** Only codes the API actually returned are shown; an unknown code gets a generic line. */
export function warningLabel(w: ContentWarning): string {
  switch (w.code) {
    case 'PAGES_WITHOUT_TEXT':
      return `Some pages have no readable text${pagesText(w.pages)}. They may be scanned images, so questions about them cannot be answered.`;
    case 'UNMAPPED_GLYPHS':
      return `Some characters could not be read${pagesText(w.pages)}. Check this text against the original.`;
    case 'NO_HEADINGS_DETECTED':
      return 'No headings were detected, so the text may be less well organized.';
    case 'BOILERPLATE_REMOVED':
      return 'Repeated headers and footers were removed (listed below).';
    case 'CONVERTER_WARNING':
      return `The converter reported a problem${pagesText(w.pages)}. Check this text against the original.`;
    default:
      return 'The system noted a problem with this document. Check the text against the original.';
  }
}

export function removedKindLabel(kind: string | null): string {
  switch (kind) {
    case 'header':
      return 'Header';
    case 'footer':
      return 'Footer';
    default:
      return 'Repeated block';
  }
}

/** Where the original opens: the native viewer takes the page from the URL fragment. */
export function pdfUrlAtPage(url: string, page: number | null): string {
  const base = url.split('#')[0];
  return page && Number.isInteger(page) && page > 0 ? `${base}#page=${page}` : base;
}
