import { describe, expect, it } from 'vitest';
import type { ProcessingChunk } from '@/lib/api/types';
import { filterChunkGroups, formatPageRange, groupChunks, piecesOf, reportPages, utf16Offsets } from './chunks';
import { signalLines, ruleLabel } from './report-labels';

function chunk(ordinal: number, charStart: number, charEnd: number, chunkType: ProcessingChunk['chunkType'] = 'SECTION', tokenCount = 10): ProcessingChunk {
  return { ordinal, chunkType, sectionPath: [], pageStart: null, pageEnd: null, charStart, charEnd, tokenCount };
}

describe('utf16Offsets', () => {
  it('counts an astral character as one code point and two code units', () => {
    const text = 'a😀b';
    const map = utf16Offsets(text, [0, 1, 2, 3]);
    expect([...map.entries()]).toEqual([[0, 0], [1, 1], [2, 3], [3, 4]]);
  });

  it('keeps Vietnamese diacritics at one unit each', () => {
    const map = utf16Offsets('Mục đích', [4, 8]);
    expect(map.get(4)).toBe(4);
    expect(map.get(8)).toBe(8);
  });

  it('clamps an offset past the end of the text', () => {
    expect(utf16Offsets('abc', [10]).get(10)).toBe(3);
  });
});

describe('groupChunks', () => {
  const text = 'x'.repeat(100);

  it('returns nothing for no chunks', () => {
    expect(groupChunks([], text)).toEqual([]);
  });

  it('keeps disjoint chunks apart, ordered by position', () => {
    const groups = groupChunks([chunk(1, 40, 60), chunk(0, 0, 40)], text);
    expect(groups.map((g) => [g.start, g.end, g.label])).toEqual([[0, 40, '#1'], [40, 60, '#2']]);
  });

  it('merges chunks that share a range (a split table row or step) into one outline', () => {
    const groups = groupChunks([chunk(2, 50, 80, 'PROCEDURE_STEP', 30), chunk(3, 50, 80, 'PROCEDURE_STEP', 25), chunk(4, 50, 80, 'PROCEDURE_STEP', 5)], text);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ label: '#3-#5', tokens: 60, ordinals: [2, 3, 4], key: 2 });
  });

  it('merges overlapping ranges and extends to the furthest end', () => {
    const groups = groupChunks([chunk(0, 0, 30), chunk(1, 20, 45)], text);
    expect(groups).toHaveLength(1);
    expect([groups[0].start, groups[0].end]).toEqual([0, 45]);
  });

  it('converts code points to UTF-16 so a slice lands on the same text', () => {
    const md = '😀😀 abc';
    const [g] = groupChunks([chunk(0, 3, 6)], md);
    expect(md.slice(g.start, g.end)).toBe('abc');
  });

  it('drops a chunk whose range is empty after clamping', () => {
    expect(groupChunks([chunk(0, 500, 600)], text)).toEqual([]);
  });

  it('preserves sectionPath and merges page ranges across grouped chunks', () => {
    const c1: ProcessingChunk = {
      ordinal: 0,
      chunkType: 'TABLE',
      sectionPath: ['3. Procedure', '3.2 Tolerance'],
      pageStart: 2,
      pageEnd: 3,
      charStart: 0,
      charEnd: 40,
      tokenCount: 20,
    };
    const c2: ProcessingChunk = {
      ordinal: 1,
      chunkType: 'TABLE',
      sectionPath: [],
      pageStart: 3,
      pageEnd: 4,
      charStart: 0,
      charEnd: 40,
      tokenCount: 15,
    };
    const [g] = groupChunks([c1, c2], text);
    expect(g.sectionPath).toEqual(['3. Procedure', '3.2 Tolerance']);
    expect(g.pageStart).toBe(2);
    expect(g.pageEnd).toBe(4);
    expect(formatPageRange(g.pageStart, g.pageEnd)).toBe('p.2–4');
    expect(formatPageRange(3, 3)).toBe('p.3');
    expect(formatPageRange(null, null)).toBeNull();
  });
});

describe('filterChunkGroups', () => {
  const md = 'Intro text about scope.\n| A | B |\nCalibration steps here.';
  const groups = groupChunks(
    [
      { ordinal: 0, chunkType: 'SECTION', sectionPath: ['1. Scope'], pageStart: 1, pageEnd: 1, charStart: 0, charEnd: 23, tokenCount: 12 },
      { ordinal: 1, chunkType: 'TABLE', sectionPath: ['2. Limits'], pageStart: 1, pageEnd: 1, charStart: 24, charEnd: 33, tokenCount: 8 },
      { ordinal: 2, chunkType: 'PROCEDURE_STEP', sectionPath: ['3. Calibration'], pageStart: 2, pageEnd: 2, charStart: 34, charEnd: 57, tokenCount: 15 },
    ],
    md,
  );

  it('filters by chunk type and by sectionPath or text query', () => {
    expect(filterChunkGroups(groups, md, { type: 'TABLE' }).map((g) => g.label)).toEqual(['#2']);
    expect(filterChunkGroups(groups, md, { query: 'limits' }).map((g) => g.label)).toEqual(['#2']);
    expect(filterChunkGroups(groups, md, { query: 'calibration' }).map((g) => g.label)).toEqual(['#3']);
    expect(filterChunkGroups(groups, md, { query: '#1' }).map((g) => g.label)).toEqual(['#1']);
  });
});

describe('reportPages', () => {
  const groups = groupChunks([0, 1, 2, 3, 4].map((i) => chunk(i, i * 20, i * 20 + 20)), 'x'.repeat(100));

  it('uses real pages for a PDF and skips text before the first page', () => {
    const pages = [
      { page: 1, charStart: 10, charEnd: 50, charStart16: 10, charEnd16: 50 },
      { page: 2, charStart: 50, charEnd: 100, charStart16: 50, charEnd16: 100 },
    ];
    expect(reportPages(100, pages, groups)).toEqual([
      { label: 'Page 1', start: 10, end: 50 },
      { label: 'Page 2', start: 50, end: 100 },
    ]);
  });

  it('cuts a Markdown file into parts that end where a group ends', () => {
    const parts = reportPages(100, [], groups, 2);
    expect(parts).toEqual([
      { label: 'Part 1', start: 0, end: 40 },
      { label: 'Part 2', start: 40, end: 80 },
      { label: 'Part 3', start: 80, end: 100 },
    ]);
  });

  it('gives one part when there are no chunks, and none for empty text', () => {
    expect(reportPages(50, [], [])).toEqual([{ label: 'Part 1', start: 0, end: 50 }]);
    expect(reportPages(0, [], [])).toEqual([]);
  });
});

describe('piecesOf', () => {
  const groups = groupChunks([chunk(0, 10, 30), chunk(1, 30, 70), chunk(2, 80, 90)], 'x'.repeat(100));

  it('alternates text and chunks and covers the whole page', () => {
    const pieces = piecesOf({ start: 0, end: 100 }, groups);
    expect(pieces.map((p) => [p.type, p.start, p.end])).toEqual([
      ['text', 0, 10], ['chunk', 10, 30], ['chunk', 30, 70], ['text', 70, 80], ['chunk', 80, 90], ['text', 90, 100],
    ]);
  });

  it('clips a chunk that crosses the page edge and says so', () => {
    const pieces = piecesOf({ start: 50, end: 100 }, groups);
    const first = pieces[0];
    expect(first).toMatchObject({ type: 'chunk', start: 50, end: 70, cutBefore: true, cutAfter: false });
    const head = piecesOf({ start: 0, end: 60 }, groups).find((p) => p.type === 'chunk' && p.group.key === 1);
    expect(head).toMatchObject({ cutAfter: true });
  });

  it('is only text when no chunk touches the page', () => {
    expect(piecesOf({ start: 70, end: 78 }, groups)).toEqual([{ type: 'text', start: 70, end: 78 }]);
  });
});

describe('labels', () => {
  it('names the evidence and tolerates a missing one', () => {
    const lines = signalLines({
      signals: { headings: 9, articleHeadings: 0, articleLines: 2, sopSectionWords: ['muc dich', 'pham vi'], procedureTables: 1 },
      language: 'vi',
      docCode: 'QT-07',
    });
    expect(lines).toContain('SOP section words: muc dich, pham vi');
    expect(lines).toContain('2 article lines in the body text');
    expect(lines).toContain('1 step table');
    expect(lines).toContain('Document code: QT-07');
    expect(signalLines({ signals: null, language: null, docCode: null })).toHaveLength(1);
  });

  it('falls back to the id for a rule it does not know', () => {
    expect(ruleLabel('NEW_RULE')).toEqual({ title: 'NEW_RULE', detail: '' });
    expect(ruleLabel('PACK').title).toMatch(/Pack/);
  });
});
