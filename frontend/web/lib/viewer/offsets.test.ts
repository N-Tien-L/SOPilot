import { describe, expect, it } from 'vitest';
import {
  citationRange,
  codePointToUtf16,
  overlaps,
  pageAt,
  pageSegments,
  snapToCodePoint,
  splitByRange,
  utf16ToCodePoint,
  type PageEntry,
} from './offsets';

// Each emoji below is one code point and two UTF-16 units.
const E = String.fromCodePoint(0x1f600);
const TEXT = `ab${E}cd${E}${E}ef`; // points: a0 b1 E2 c3 d4 E5 E6 e7 f8

describe('codePointToUtf16', () => {
  it('is the identity on text without astral characters', () => {
    expect(codePointToUtf16('Quy trình mua hàng', 7)).toBe(7);
    expect(codePointToUtf16('Quy trình', 0)).toBe(0);
  });

  it('counts an emoji as two units', () => {
    expect(codePointToUtf16(TEXT, 2)).toBe(2);
    expect(codePointToUtf16(TEXT, 3)).toBe(4);
    expect(codePointToUtf16(TEXT, 5)).toBe(6);
    expect(codePointToUtf16(TEXT, 7)).toBe(10);
  });

  it('clamps beyond the text and ignores bad input', () => {
    expect(codePointToUtf16(TEXT, 999)).toBe(TEXT.length);
    expect(codePointToUtf16(TEXT, -3)).toBe(0);
    expect(codePointToUtf16(TEXT, Number.NaN)).toBe(0);
  });

  it('keeps a lone surrogate as one point', () => {
    expect(codePointToUtf16('a\ud83dz', 2)).toBe(2);
  });
});

describe('utf16ToCodePoint', () => {
  it('inverts codePointToUtf16 on pair boundaries', () => {
    for (let cp = 0; cp <= 9; cp += 1) {
      expect(utf16ToCodePoint(TEXT, codePointToUtf16(TEXT, cp))).toBe(cp);
    }
  });

  it('counts a position inside a pair as the pair', () => {
    expect(utf16ToCodePoint(TEXT, 3)).toBe(3);
  });
});

describe('snapToCodePoint', () => {
  it('moves an index inside a surrogate pair back to its start', () => {
    expect(snapToCodePoint(TEXT, 3)).toBe(2);
    expect(snapToCodePoint(TEXT, 2)).toBe(2);
    expect(snapToCodePoint(TEXT, 4)).toBe(4);
  });
});

describe('citationRange', () => {
  it('maps code points to units with emoji before and inside the range', () => {
    const range = citationRange(TEXT, 3, 7);
    expect(range).toEqual({ start: 4, end: 10 });
    expect(TEXT.slice(range!.start, range!.end)).toBe(`cd${E}${E}`);
  });

  it('shows a naive slice at code point offsets would be wrong', () => {
    expect(TEXT.slice(3, 7)).not.toBe(`cd${E}${E}`);
  });

  it('returns null for unusable offsets', () => {
    expect(citationRange(TEXT, -1, 4)).toBeNull();
    expect(citationRange(TEXT, 5, 5)).toBeNull();
    expect(citationRange(TEXT, 6, 2)).toBeNull();
    expect(citationRange(TEXT, 1.5, 4)).toBeNull();
    expect(citationRange(TEXT, 50, 60)).toBeNull();
  });

  it('clamps an end past the text', () => {
    expect(citationRange(TEXT, 7, 99)).toEqual({ start: 10, end: TEXT.length });
  });

  it('keeps BMP text (Vietnamese, precomposed and combining marks) as the identity', () => {
    const vi = 'Quy trình mua hàng ệ';
    expect(citationRange(vi, 4, 10)).toEqual({ start: 4, end: 10 });
    const decomposed = 'ệ x';
    expect(citationRange(decomposed, 0, 3)).toEqual({ start: 0, end: 3 });
  });
});

describe('splitByRange', () => {
  it('cuts around the highlight', () => {
    expect(splitByRange(TEXT, { start: 4, end: 10 })).toEqual({ before: `ab${E}`, hit: `cd${E}${E}`, after: 'ef' });
  });

  it('never cuts an emoji in half', () => {
    const { before, hit, after } = splitByRange(TEXT, { start: 3, end: 5 });
    expect(before + hit + after).toBe(TEXT);
    expect(before).toBe('ab');
    expect(hit).toBe(`${E}c`);
  });

  it('returns the text unchanged without a range', () => {
    expect(splitByRange('abc', null)).toEqual({ before: 'abc', hit: '', after: '' });
  });
});

describe('overlaps', () => {
  it('treats ranges as half-open', () => {
    expect(overlaps(0, 5, 5, 8)).toBe(false);
    expect(overlaps(0, 6, 5, 8)).toBe(true);
    expect(overlaps(5, 8, 0, 5)).toBe(false);
  });
});

describe('pages', () => {
  const pages: PageEntry[] = [
    { page: 1, charStart: 0, charEnd: 4, charStart16: 0, charEnd16: 5 },
    { page: 2, charStart: 4, charEnd: 9, charStart16: 5, charEnd16: 11 },
  ];

  it('splits into one segment per page and covers the whole text', () => {
    expect(pageSegments(12, pages)).toEqual([
      { page: 1, start: 0, end: 5 },
      { page: 2, start: 5, end: 12 },
    ]);
  });

  it('keeps text before the first page and handles no pages', () => {
    expect(pageSegments(20, [{ page: 1, charStart: 3, charEnd: 9, charStart16: 4, charEnd16: 10 }])).toEqual([
      { page: null, start: 0, end: 4 },
      { page: 1, start: 4, end: 20 },
    ]);
    expect(pageSegments(7, [])).toEqual([{ page: null, start: 0, end: 7 }]);
    expect(pageSegments(0, [])).toEqual([]);
  });

  it('repairs unordered pages', () => {
    expect(pageSegments(12, [...pages].reverse()).map((s) => s.page)).toEqual([1, 2]);
  });

  it('finds the page of an offset using the UTF-16 bounds', () => {
    expect(pageAt(pages, 0)).toBe(1);
    expect(pageAt(pages, 4)).toBe(1);
    expect(pageAt(pages, 5)).toBe(2);
    expect(pageAt(pages, 11)).toBeNull();
  });
});
