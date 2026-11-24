import { describe, expect, it } from 'vitest';
import { canOpenViewer, citeNumber, linkCitations } from './citations';
import { clearWarnings, recallNearest, recallWarnings, rememberNearest, rememberWarnings } from './warning-store';
import { formatBytes, gapFlags, refusalCopy, warningText } from './labels';

describe('linkCitations', () => {
  it('turns known markers into cite links and keeps the surrounding text', () => {
    expect(linkCitations('Wear boots [1]. Gloves [2] too.', new Set([1, 2]))).toBe(
      'Wear boots [1](cite:1). Gloves [2](cite:2) too.',
    );
  });

  it('leaves an unknown marker and an existing link untouched', () => {
    expect(linkCitations('See [4] and [1]', new Set([1]))).toBe('See [4] and [1](cite:1)');
    expect(linkCitations('A [1](https://x.test) link', new Set([1]))).toBe('A [1](https://x.test) link');
  });

  it('handles adjacent markers and Vietnamese text', () => {
    expect(linkCitations('[1][2]', new Set([1, 2]))).toBe('[1](cite:1)[2](cite:2)');
    expect(linkCitations('Đồng phục bảo hộ [1]', new Set([1]))).toBe('Đồng phục bảo hộ [1](cite:1)');
  });
});

describe('citeNumber', () => {
  it('reads only cite: hrefs', () => {
    expect(citeNumber('cite:3')).toBe(3);
    expect(citeNumber('https://example.com')).toBeNull();
    expect(citeNumber('cite:x')).toBeNull();
    expect(citeNumber(undefined)).toBeNull();
  });
});

describe('canOpenViewer', () => {
  it('blocks only an explicitly old version', () => {
    expect(canOpenViewer({ isCurrentVersion: false })).toBe(false);
    expect(canOpenViewer({ isCurrentVersion: true })).toBe(true);
    expect(canOpenViewer({})).toBe(true);
  });
});

describe('refusalCopy', () => {
  it('shows the closest documents only for NO_EVIDENCE', () => {
    expect(refusalCopy('NO_EVIDENCE').showNearest).toBe(true);
    expect(refusalCopy('OUT_OF_SCOPE').showNearest).toBe(false);
    expect(refusalCopy('INPUT_INVALID').showNearest).toBe(false);
    expect(refusalCopy('SOMETHING_NEW').showNearest).toBe(false);
  });
});

describe('labels', () => {
  it('warns about figures for NUMBER_NOT_IN_SOURCES', () => {
    expect(warningText({ code: 'NUMBER_NOT_IN_SOURCES', values: ['12'] })).toMatch(/figures/);
  });

  it('describes why a gap was flagged', () => {
    expect(gapFlags({ refusalReason: 'NO_EVIDENCE', downvotes: 0 })).toEqual(['No evidence']);
    expect(gapFlags({ refusalReason: null, downvotes: 2 })).toEqual(['2 downvotes']);
    expect(gapFlags({ refusalReason: null, downvotes: 0 })).toEqual(['Flagged']);
  });

  it('formats sizes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(80 * 1024 * 1024)).toBe('80.0 MB');
  });
});

describe('warning store', () => {
  it('keeps warnings per message until cleared', () => {
    rememberWarnings('m1', [{ code: 'NUMBER_NOT_IN_SOURCES', values: ['5'] }]);
    rememberWarnings('m2', []);
    expect(recallWarnings('m1')).toHaveLength(1);
    expect(recallWarnings('m2')).toEqual([]);
    clearWarnings();
    expect(recallWarnings('m1')).toEqual([]);
  });

  it('keeps the closest documents of a refusal per message until cleared', () => {
    rememberNearest('m3', [{ documentId: 'd1', title: 'SOP-Safety' }]);
    expect(recallNearest('m3')).toEqual([{ documentId: 'd1', title: 'SOP-Safety' }]);
    expect(recallNearest('other')).toEqual([]);
    clearWarnings();
    expect(recallNearest('m3')).toEqual([]);
  });
});
