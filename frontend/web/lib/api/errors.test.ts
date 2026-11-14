import { describe, expect, it } from 'vitest';
import {
  ApiError,
  NETWORK_ERROR_MESSAGE,
  describeError,
  networkError,
  parseAiError,
  parseCoreError,
} from './errors';

describe('core-api error adapter', () => {
  it('reads code, fixed message, details and traceId from the envelope', () => {
    const error = parseCoreError(
      409,
      { error: { code: 'QUOTA_EXCEEDED', message: 'Document quota reached.', details: { limit: 50 } }, traceId: 'trace-1' },
      null,
    );
    expect(error).toMatchObject({
      status: 409,
      code: 'QUOTA_EXCEEDED',
      message: 'Document quota reached.',
      traceId: 'trace-1',
      details: { limit: 50 },
    });
  });

  it('falls back to the X-Trace-Id header and a fixed message for unknown shapes', () => {
    const error = parseCoreError(500, '<html>boom</html>', 'hdr-trace-9');
    expect(error.message).toBe('Something went wrong. Please try again.');
    expect(error.traceId).toBe('hdr-trace-9');
    expect(error.code).toBeNull();
  });

  it('never shows an oversized or non-string message', () => {
    expect(parseCoreError(400, { error: { message: 'x'.repeat(500) } }).message).toBe('The request was not valid.');
    expect(parseCoreError(404, { error: { message: { stack: 'at Foo' } } }).message).toBe('Not found.');
  });
});

describe('ai-service error adapter', () => {
  it('uses the fixed detail sentence and has no code or traceId', () => {
    const error = parseAiError(401, { detail: 'authentication required' });
    expect(error).toMatchObject({ status: 401, message: 'authentication required', code: null, traceId: null });
  });

  it('does not show a FastAPI validation list', () => {
    const error = parseAiError(422, { detail: [{ loc: ['body', 'content'], msg: 'too long' }] });
    expect(error.message).toBe('The request was not valid.');
  });

  it('maps 503 to a fixed local sentence when detail is missing', () => {
    expect(parseAiError(503, undefined).message).toBe('This service is not available right now.');
  });
});

describe('describeError', () => {
  it('returns message and traceId for ApiError, a fixed string for anything else', () => {
    expect(describeError(new ApiError(500, 'Server error.', 'INTERNAL_ERROR', 't-1'))).toEqual({
      message: 'Server error.',
      traceId: 't-1',
    });
    expect(describeError(new Error('TypeError: x is undefined at app.js:1'))).toEqual({
      message: 'Something went wrong. Please try again.',
      traceId: null,
    });
    expect(networkError().message).toBe(NETWORK_ERROR_MESSAGE);
  });
});
