import { describe, expect, it } from 'vitest';
import { buildAnswerBody } from './stream';

describe('buildAnswerBody', () => {
  it('omits rerank when undefined or true', () => {
    expect(buildAnswerBody({ content: 'q' })).toEqual({ content: 'q', includeTrace: true });
    expect(buildAnswerBody({ content: 'q', rerank: true })).toEqual({ content: 'q', includeTrace: true });
    expect('rerank' in buildAnswerBody({ content: 'q', rerank: true })).toBe(false);
  });

  it('sends rerank:false only when switched off', () => {
    expect(buildAnswerBody({ content: 'q', rerank: false })).toEqual({
      content: 'q',
      includeTrace: true,
      rerank: false,
    });
  });

  it('keeps includeTrace and lang unchanged', () => {
    expect(buildAnswerBody({ content: 'q', lang: 'vi', rerank: false })).toEqual({
      content: 'q',
      includeTrace: true,
      lang: 'vi',
      rerank: false,
    });
  });
});
