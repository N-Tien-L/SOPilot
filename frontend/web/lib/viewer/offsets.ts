// Pure offset logic for the recognized-content view and the citation viewer (FR-14, FR-31, R5).
//
// JavaScript strings index by UTF-16 code unit; the ai-service stores offsets as Unicode code
// points (Python indexes). A character outside the BMP (an emoji) is one code point but two code
// units, so the two differ as soon as one appears before the offset. The content response carries
// both for pages (`charStart` / `charStart16`); a citation carries only code points, so the viewer
// converts it here against the same canonical Markdown.

export interface Range16 {
  /** UTF-16 code unit index, inclusive. */
  start: number;
  /** UTF-16 code unit index, exclusive. */
  end: number;
}

export interface PageEntry {
  page: number;
  charStart: number;
  charEnd: number;
  charStart16: number;
  charEnd16: number;
}

function isHighSurrogate(code: number): boolean {
  return code >= 0xd800 && code <= 0xdbff;
}

function isLowSurrogate(code: number): boolean {
  return code >= 0xdc00 && code <= 0xdfff;
}

function stepAt(text: string, i: number): number {
  return isHighSurrogate(text.charCodeAt(i)) && isLowSurrogate(text.charCodeAt(i + 1)) ? 2 : 1;
}

/** Code unit length of the first `cp` code points of `text` (clamped to the text). */
export function codePointToUtf16(text: string, cp: number): number {
  if (!Number.isFinite(cp) || cp <= 0) return 0;
  let units = 0;
  let points = 0;
  while (points < cp && units < text.length) {
    units += stepAt(text, units);
    points += 1;
  }
  return units;
}

/** Number of code points before code unit `unit` (a position inside a pair counts the pair). */
export function utf16ToCodePoint(text: string, unit: number): number {
  const stop = Math.min(Math.max(0, Math.floor(unit)), text.length);
  let points = 0;
  let i = 0;
  while (i < stop) {
    i += stepAt(text, i);
    points += 1;
  }
  return points;
}

/** A code unit index never splits a surrogate pair: inside one, it moves back to the pair start. */
export function snapToCodePoint(text: string, unit: number): number {
  const i = Math.min(Math.max(0, Math.floor(unit)), text.length);
  if (i > 0 && i < text.length && isLowSurrogate(text.charCodeAt(i)) && isHighSurrogate(text.charCodeAt(i - 1))) {
    return i - 1;
  }
  return i;
}

/**
 * The range of a citation (code point offsets, `[charStart, charEnd)`) as UTF-16 offsets into the
 * canonical Markdown. Null when the offsets are not usable (negative, reversed, outside the text).
 */
export function citationRange(markdown: string, charStart: number, charEnd: number): Range16 | null {
  if (!Number.isInteger(charStart) || !Number.isInteger(charEnd) || charStart < 0 || charEnd <= charStart) {
    return null;
  }
  const start = codePointToUtf16(markdown, charStart);
  if (start >= markdown.length) return null;
  const end = codePointToUtf16(markdown, charEnd);
  return end > start ? { start, end } : null;
}

export interface RangeSplit {
  before: string;
  hit: string;
  after: string;
}

/** Splits `text` around `range`; with no range everything is `before`. */
export function splitByRange(text: string, range: Range16 | null): RangeSplit {
  if (!range) return { before: text, hit: '', after: '' };
  const start = snapToCodePoint(text, range.start);
  const end = snapToCodePoint(text, Math.max(range.end, start));
  return { before: text.slice(0, start), hit: text.slice(start, end), after: text.slice(end) };
}

/** Half-open ranges `[a0, a1)` and `[b0, b1)` share at least one unit. */
export function overlaps(a0: number, a1: number, b0: number, b1: number): boolean {
  return a0 < b1 && b0 < a1;
}

export interface Segment {
  /** Page number, or null for text before the first page. */
  page: number | null;
  start: number;
  end: number;
}

/**
 * Splits the Markdown (length in code units) into one segment per page using `charStart16`, so each
 * page can be rendered under its "Page N" marker. Text before the first page is its own segment.
 * Pages are expected ordered and disjoint; anything else is repaired by sorting and clamping.
 */
export function pageSegments(length: number, pages: readonly PageEntry[]): Segment[] {
  if (pages.length === 0) return length > 0 ? [{ page: null, start: 0, end: length }] : [];
  const sorted = [...pages].sort((a, b) => a.charStart16 - b.charStart16);
  const clamp = (n: number) => Math.min(Math.max(0, n), length);
  const out: Segment[] = [];
  const firstStart = clamp(sorted[0].charStart16);
  if (firstStart > 0) out.push({ page: null, start: 0, end: firstStart });
  sorted.forEach((p, i) => {
    const start = i === 0 ? firstStart : clamp(p.charStart16);
    const next = sorted[i + 1];
    const end = next ? Math.max(start, clamp(next.charStart16)) : length;
    out.push({ page: p.page, start, end });
  });
  return out;
}

/** The page a UTF-16 offset falls in, or null when no page covers it. */
export function pageAt(pages: readonly PageEntry[], offset: number): number | null {
  for (const p of pages) {
    if (offset >= p.charStart16 && offset < p.charEnd16) return p.page;
  }
  return null;
}
