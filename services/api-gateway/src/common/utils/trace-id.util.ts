import * as crypto from 'crypto';

export const TRACE_ID_HEADER = 'X-Trace-ID';

export function generateTraceId(): string {
  return crypto.randomUUID();
}

export function getTraceId(request: {
  headers: { [key: string]: string };
}): string {
  const existingTraceId = request.headers[TRACE_ID_HEADER.toLowerCase()];
  return existingTraceId || generateTraceId();
}

export function sanitizeLogData(
  data: Record<string, unknown>,
): Record<string, unknown> {
  const sanitized = { ...data };
  const sensitiveFields = [
    'password',
    'newPassword',
    'currentPassword',
    'confirmPassword',
    'accessToken',
    'refreshToken',
    'token',
    'authorization',
    'bearer',
    'cookie',
    'secret',
    'apiKey',
    'apikey',
    'ssn',
    'creditCard',
    'cvv',
  ];

  for (const key of Object.keys(sanitized)) {
    const lowerKey = key.toLowerCase();
    if (sensitiveFields.some((field) => lowerKey.includes(field))) {
      sanitized[key] = '[REDACTED]';
    }
  }

  return sanitized;
}
