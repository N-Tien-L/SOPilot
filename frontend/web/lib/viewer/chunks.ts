// Pure logic for the processing report (V2-46): chunks on the canonical Markdown, grouped and cut per page.
//
// The ai-service gives each chunk a code point range. Ranges are not unique: a split table row or a split
// procedure step repeats the whole row's range, so chunks that share or overlap a range are drawn as one
// outline. Everything here works in UTF-16 code units, the ones a browser string uses.

import type { ChunkType, ProcessingChunk } from '@/lib/api/types';
import { pageSegments, type PageEntry } from './offsets';

export interface ChunkGroup {
  /** Stable key: the first ordinal. */
  key: number;
  ordinals: number[];
  /** `#3` for one chunk, `#12-#14` for several that share a range (ordinals shown from 1). */
  label: string;
  chunkType: ChunkType;
  /** UTF-16 start/end offsets on canonical Markdown. */
  start: number;
  end: number;
  /** Original Unicode code-point offsets from ai-service. */
  charStart: number;
  charEnd: number;
  tokens: number;
  /** Heading hierarchy path from the first chunk in the group. */
  sectionPath: string[];
  /** Min/max page numbers covered by the group (null for Markdown documents without pages). */
  pageStart: number | null;
  pageEnd: number | null;
}

export interface ReportPage {
  label: string;
  start: number;
  end: number;
}

export type Piece =
  | { type: 'text'; start: number; end: number }
  | { type: 'chunk'; group: ChunkGroup; start: number; end: number; cutBefore: boolean; cutAfter: boolean };

/** UTF-16 index of each requested code point index, in one pass over the text. */
export function utf16Offsets(text: string, codePoints: readonly number[]): Map<number, number> {
  const wanted = [...new Set(codePoints)].sort((a, b) => a - b);
  const out = new Map<number, number>();
  let units = 0;
  let points = 0;
  for (const target of wanted) {
    while (points < target && units < text.length) {
      const code = text.charCodeAt(units);
      const pair = code >= 0xd800 && code <= 0xdbff && units + 1 < text.length;
      units += pair ? 2 : 1;
      points += 1;
    }
    out.set(target, units);
  }
  return out;
}

function labelOf(ordinals: number[]): string {
  const first = ordinals[0] + 1;
  const last = ordinals[ordinals.length - 1] + 1;
  return first === last ? `#${first}` : `#${first}-#${last}`;
}

function minPage(a: number | null, b: number | null): number | null {
  if (a === null) return b;
  if (b === null) return a;
  return Math.min(a, b);
}

function maxPage(a: number | null, b: number | null): number | null {
  if (a === null) return b;
  if (b === null) return a;
  return Math.max(a, b);
}

/** Chunks that share or overlap a range become one group; the result is sorted and disjoint. */
export function groupChunks(chunks: readonly ProcessingChunk[], markdown: string): ChunkGroup[] {
  if (chunks.length === 0) return [];
  const offsets = utf16Offsets(markdown, chunks.flatMap((c) => [c.charStart, c.charEnd]));
  const items = chunks
    .map((c) => ({
      c,
      start: offsets.get(c.charStart) ?? 0,
      end: offsets.get(c.charEnd) ?? markdown.length,
    }))
    .filter((i) => i.end > i.start)
    .sort((a, b) => a.start - b.start || a.end - b.end || a.c.ordinal - b.c.ordinal);

  const groups: ChunkGroup[] = [];
  for (const { c, start, end } of items) {
    const last = groups[groups.length - 1];
    if (last && start < last.end) {
      last.ordinals.push(c.ordinal);
      last.end = Math.max(last.end, end);
      last.charStart = Math.min(last.charStart, c.charStart);
      last.charEnd = Math.max(last.charEnd, c.charEnd);
      last.tokens += c.tokenCount;
      last.pageStart = minPage(last.pageStart, c.pageStart);
      last.pageEnd = maxPage(last.pageEnd, c.pageEnd);
      if (last.sectionPath.length === 0 && c.sectionPath.length > 0) {
        last.sectionPath = [...c.sectionPath];
      }
      continue;
    }
    groups.push({
      key: c.ordinal,
      ordinals: [c.ordinal],
      label: '',
      chunkType: c.chunkType,
      start,
      end,
      charStart: c.charStart,
      charEnd: c.charEnd,
      tokens: c.tokenCount,
      sectionPath: [...c.sectionPath],
      pageStart: c.pageStart,
      pageEnd: c.pageEnd,
    });
  }
  for (const g of groups) {
    g.ordinals.sort((a, b) => a - b);
    g.key = g.ordinals[0];
    g.label = labelOf(g.ordinals);
  }
  return groups;
}

/** Formats a group's page range as `p.3`, `p.3–4`, or null when the document has no page numbers. */
export function formatPageRange(pageStart: number | null, pageEnd: number | null): string | null {
  if (pageStart === null && pageEnd === null) return null;
  const start = pageStart ?? pageEnd!;
  const end = pageEnd ?? start;
  return start === end ? `p.${start}` : `p.${start}–${end}`;
}

/** Client-side filter over chunk groups by ChunkType and substring match on sectionPath, label, or text. */
export function filterChunkGroups(
  groups: readonly ChunkGroup[],
  markdown: string,
  opts: { type?: ChunkType | 'ALL'; query?: string },
): ChunkGroup[] {
  const type = opts.type ?? 'ALL';
  const needle = (opts.query ?? '').trim().toLowerCase();
  return groups.filter((g) => {
    if (type !== 'ALL' && g.chunkType !== type) return false;
    if (!needle) return true;
    if (g.label.toLowerCase().includes(needle)) return true;
    if (g.sectionPath.some((p) => p.toLowerCase().includes(needle))) return true;
    return markdown.slice(g.start, g.end).toLowerCase().includes(needle);
  });
}

/**
 * The pages the picker offers. A PDF uses its real pages; a Markdown file has none, so it is cut into
 * parts of `perPage` groups (each part ends where its last group ends).
 */
export function reportPages(
  length: number,
  pages: readonly PageEntry[],
  groups: readonly ChunkGroup[],
  perPage = 6,
): ReportPage[] {
  if (length <= 0) return [];
  if (pages.length > 0) {
    return pageSegments(length, pages)
      .filter((s) => s.page !== null && s.end > s.start)
      .map((s) => ({ label: `Page ${s.page}`, start: s.start, end: s.end }));
  }
  if (groups.length === 0) return [{ label: 'Part 1', start: 0, end: length }];
  const parts: ReportPage[] = [];
  let start = 0;
  for (let i = 0; i < groups.length; i += perPage) {
    const lastOfPart = groups[Math.min(i + perPage, groups.length) - 1];
    const end = i + perPage >= groups.length ? length : lastOfPart.end;
    parts.push({ label: `Part ${parts.length + 1}`, start, end });
    start = end;
  }
  return parts;
}

/** The slice of one page as plain text and chunk outlines, in order; groups are clipped to the page. */
export function piecesOf(page: { start: number; end: number }, groups: readonly ChunkGroup[]): Piece[] {
  const out: Piece[] = [];
  let at = page.start;
  for (const g of groups) {
    if (g.end <= page.start) continue;
    if (g.start >= page.end) break;
    const start = Math.max(g.start, page.start);
    const end = Math.min(g.end, page.end);
    if (start > at) out.push({ type: 'text', start: at, end: start });
    out.push({ type: 'chunk', group: g, start, end, cutBefore: g.start < page.start, cutAfter: g.end > page.end });
    at = end;
  }
  if (at < page.end) out.push({ type: 'text', start: at, end: page.end });
  return out;
}
