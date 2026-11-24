import { describe, expect, it } from 'vitest';
import { effectiveRerank, readRerankPreference, writeRerankPreference, type PreferenceStorage } from './rerank-preference';

function memory(): PreferenceStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

const throwing: PreferenceStorage = {
  getItem: () => {
    throw new Error('denied');
  },
  setItem: () => {
    throw new Error('denied');
  },
  removeItem: () => {
    throw new Error('denied');
  },
};

describe('effectiveRerank', () => {
  it('is undefined when unavailable, otherwise the choice', () => {
    expect(effectiveRerank(false, true)).toBeUndefined();
    expect(effectiveRerank(false, false)).toBeUndefined();
    expect(effectiveRerank(true, true)).toBe(true);
    expect(effectiveRerank(true, false)).toBe(false);
  });
});

describe('rerank preference', () => {
  it('defaults to on', () => {
    expect(readRerankPreference(memory())).toBe(true);
  });

  it('stores off and reads it back', () => {
    const s = memory();
    writeRerankPreference(false, s);
    expect(s.data.get('sopilot.chat.rerank')).toBe('off');
    expect(readRerankPreference(s)).toBe(false);
  });

  it('writing on clears the key', () => {
    const s = memory();
    writeRerankPreference(false, s);
    writeRerankPreference(true, s);
    expect(s.data.has('sopilot.chat.rerank')).toBe(false);
    expect(readRerankPreference(s)).toBe(true);
  });

  it('falls back to on without throwing when storage throws or is missing', () => {
    expect(readRerankPreference(throwing)).toBe(true);
    expect(() => writeRerankPreference(false, throwing)).not.toThrow();
    expect(readRerankPreference(undefined)).toBe(true);
    expect(() => writeRerankPreference(false, undefined)).not.toThrow();
  });
});
