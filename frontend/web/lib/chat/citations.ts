// Pure logic for the answer view: turn `[n]` markers into citation chips (FR-12/14) and decide how
// a citation may be opened (D10: an old version never opens the viewer).

/**
 * Rewrites known `[n]` markers as Markdown links `[n](cite:n)` so the renderer can show chips
 * inside the normal text flow. An unknown marker stays literal (the server removes unmappable
 * markers; this is a safety net).
 */
export function linkCitations(text: string, known: ReadonlySet<number>): string {
  return text.replace(/\[(\d{1,3})\](?!\()/g, (match, digits: string) => {
    const n = Number(digits);
    return known.has(n) ? `[${n}](cite:${n})` : match;
  });
}

export const CITE_PREFIX = 'cite:';

/** The citation number of a `cite:n` href, or null for any other link. */
export function citeNumber(href: string | undefined): number | null {
  if (!href || !href.startsWith(CITE_PREFIX)) return null;
  const n = Number(href.slice(CITE_PREFIX.length));
  return Number.isInteger(n) && n > 0 ? n : null;
}

export interface CitationLike {
  /** Absent while streaming (the live `citations` event has no flag): treated as current. */
  isCurrentVersion?: boolean;
}

/** The viewer (V2-32) only serves the current version, so an old one shows the stored passage. */
export function canOpenViewer(citation: CitationLike): boolean {
  return citation.isCurrentVersion !== false;
}
