import { describe, expect, it } from 'vitest';
import { pdfUrlAtPage, versionNotice, warningLabel } from './labels';

const current = { id: 'v2', versionNo: 2, originalName: 'a.pdf', fileType: 'PDF', sizeBytes: 1, pageCount: 3, warningCodes: [] };

describe('versionNotice', () => {
  it('is null when the versions match or there is no current version', () => {
    expect(versionNotice({ currentVersion: current, latestVersion: { id: 'v2', versionNo: 2, status: 'READY', failureCode: null, failureMessage: null } })).toBeNull();
    expect(versionNotice({ currentVersion: null, latestVersion: { id: 'v1', versionNo: 1, status: 'PROCESSING', failureCode: null, failureMessage: null } })).toBeNull();
  });

  it('names the version used for Q&A and the newer one', () => {
    const latest = { id: 'v3', versionNo: 3, status: 'PROCESSING' as const, failureCode: null, failureMessage: null };
    expect(versionNotice({ currentVersion: current, latestVersion: latest })).toBe(
      'Version 2 is used for Q&A; version 3 is processing.',
    );
    expect(versionNotice({ currentVersion: current, latestVersion: { ...latest, status: 'FAILED' } })).toBe(
      'Version 2 is used for Q&A; version 3 failed to process.',
    );
  });
});

describe('warningLabel', () => {
  it('lists pages and falls back for unknown codes', () => {
    expect(warningLabel({ code: 'PAGES_WITHOUT_TEXT', pages: [3, 7] })).toContain('pages 3, 7');
    expect(warningLabel({ code: 'PAGES_WITHOUT_TEXT', pages: [3] })).toContain('page 3');
    expect(warningLabel({ code: 'SOMETHING_NEW' })).toContain('Check the text');
  });
});

describe('pdfUrlAtPage', () => {
  it('sets the page fragment and replaces an old one', () => {
    expect(pdfUrlAtPage('https://h/o?sig=1', 4)).toBe('https://h/o?sig=1#page=4');
    expect(pdfUrlAtPage('https://h/o?sig=1#page=2', 5)).toBe('https://h/o?sig=1#page=5');
    expect(pdfUrlAtPage('https://h/o?sig=1#page=2', null)).toBe('https://h/o?sig=1');
    expect(pdfUrlAtPage('https://h/o', 0)).toBe('https://h/o');
  });
});
