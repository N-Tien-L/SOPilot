import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  RequestTimeoutException,
} from '@nestjs/common';
import { Observable, timeout, catchError } from 'rxjs';
import type { Request } from 'express';

@Injectable()
export class TimeoutInterceptor implements NestInterceptor {
  private readonly defaultTimeoutMs = 30000;
  private readonly longTimeoutMs = 120000;

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const request = context.switchToHttp().getRequest<Request>();
    const path = request?.path || request?.url || '';

    const isLongRunning =
      path.includes('/preview') ||
      path.includes('/download') ||
      // Document confirm is synchronous and may wait up to 60s for ingestion
      // to complete (file extraction, embedding generation, dedup checks).
      (path.includes('/documents/') && path.endsWith('/confirm'));
    const timeoutMs = isLongRunning ? this.longTimeoutMs : this.defaultTimeoutMs;

    return next.handle().pipe(
      timeout(timeoutMs),
      catchError((err) => {
        if (err instanceof Error && err.message.includes('Timeout')) {
          throw new RequestTimeoutException('Request timeout');
        }
        throw err;
      }),
    );
  }
}
