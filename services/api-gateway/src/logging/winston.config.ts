import {
  utilities as nestWinstonModuleUtilities,
  WinstonModuleOptions,
} from 'nest-winston';
import * as winston from 'winston';

const { combine, timestamp, printf, colorize, json, errors } = winston.format;

const logFormat = printf(({ level, message, timestamp, traceId, ...meta }) => {
  const logObject = {
    timestamp,
    level,
    message,
    traceId: traceId || 'no-trace-id',
    ...meta,
  };

  if (process.env.NODE_ENV === 'development') {
    const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
    return `[${timestamp}] ${level}: ${message}${metaStr}${traceId ? ` [traceId: ${traceId}]` : ''}`;
  }

  return JSON.stringify(logObject);
});

export function createWinstonConfig(): WinstonModuleOptions {
  const isProduction = process.env.NODE_ENV === 'production';

  return {
    level: process.env.LOG_LEVEL || 'info',
    format: combine(
      errors({ stack: true }),
      timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
      isProduction ? json() : combine(colorize(), logFormat),
    ),
    transports: [
      new winston.transports.Console({
        format: combine(
          timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
          isProduction ? json() : combine(colorize(), logFormat),
        ),
      }),
    ],
    defaultMeta: {
      service: 'api-gateway',
    },
    ...nestWinstonModuleUtilities.format,
  };
}
