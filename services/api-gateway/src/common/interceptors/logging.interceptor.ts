'use client';

import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  Logger,
  Optional,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import type { Request, Response } from 'express';
import { TRACE_ID_HEADER, sanitizeLogData } from '../utils';
import { IUserContext } from '../interfaces';
import { MetricsService } from '../../health/metrics/metrics.service';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  private readonly logger = new Logger('HTTP');

  constructor(
    @Optional() private readonly metricsService?: MetricsService,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const ctx = context.switchToHttp();
    const request = ctx.getRequest<Request>();
    const response = ctx.getResponse<Response>();

    const { method, url, body } = request;
    const traceId =
      (request.headers[TRACE_ID_HEADER.toLowerCase()] as string) || 'unknown';
    const user = request.user as IUserContext | undefined;
    const userId = user?.userId || 'anonymous';

    const startTime = Date.now();

    const sanitizedBody = body
      ? sanitizeLogData(body as Record<string, unknown>)
      : undefined;

    this.logger.log({
      type: 'REQUEST',
      traceId,
      method,
      url,
      userId,
      ip: request.ip || request.socket.remoteAddress,
      userAgent: request.headers['user-agent'],
      body: sanitizedBody,
    });

    return next.handle().pipe(
      tap({
        next: (data: unknown) => {
          const duration = Date.now() - startTime;
          let actualStatus = response.statusCode;
          if (data && typeof data === 'object' && '_proxied' in data) {
            const proxied = data as { _proxied: boolean; statusCode?: number };
            if (proxied.statusCode !== undefined) {
              actualStatus = proxied.statusCode;
            }
          }
          this.logger.log({
            type: 'RESPONSE',
            traceId,
            method,
            url,
            statusCode: actualStatus,
            duration,
            userId,
          });
          this.metricsService?.recordRequest({
            method,
            path: url,
            statusCode: actualStatus,
            duration,
            userId,
            traceId,
          });
        },
        error: (error: Error) => {
          const duration = Date.now() - startTime;
          let actualStatus = response.statusCode || 500;
          if (error && typeof error === 'object') {
            const errWithStatus = error as unknown as Record<string, unknown>;
            if (errWithStatus.status && typeof errWithStatus.status === 'number') {
              actualStatus = errWithStatus.status as number;
            }
            if (errWithStatus.statusCode && typeof errWithStatus.statusCode === 'number') {
              actualStatus = errWithStatus.statusCode as number;
            }
          }
          this.logger.error({
            type: 'RESPONSE_ERROR',
            traceId,
            method,
            url,
            statusCode: actualStatus,
            duration,
            userId,
            error: error.message || 'Unknown error',
            stack:
              process.env.NODE_ENV === 'development' ? error.stack : undefined,
          });
          this.metricsService?.recordRequest({
            method,
            path: url,
            statusCode: actualStatus,
            duration,
            userId,
            traceId,
          });
        },
      }),
    );
  }
}
