import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import * as crypto from 'crypto';
import type { Request, Response } from 'express';
import { TRACE_ID_HEADER } from '../utils';

@Injectable()
export class TraceIdInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const request = context.switchToHttp().getRequest<Request>();
    const response = context.switchToHttp().getResponse<Response>();

    let traceId =
      (request.headers[TRACE_ID_HEADER.toLowerCase()] as string) || '';

    if (!traceId) {
      traceId = crypto.randomUUID();
    }

    request.traceId = traceId;
    response.setHeader(TRACE_ID_HEADER, traceId);

    return next.handle().pipe(tap(() => {}));
  }
}
