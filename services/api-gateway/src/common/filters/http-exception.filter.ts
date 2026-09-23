import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { IErrorResponse, ErrorCode, ErrorResponse } from '../dto';
import { TRACE_ID_HEADER } from '../utils';

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    const traceId =
      (request.headers[TRACE_ID_HEADER.toLowerCase()] as string) || 'unknown';
    const status = this.getStatus(exception);
    const errorResponse = this.buildErrorResponse(exception, status, traceId);

    this.logger.error(
      `HTTP Error ${status} - ${errorResponse.error.message}`,
      exception instanceof Error ? exception.stack : undefined,
    );

    response.status(status).json(errorResponse);
  }

  private getStatus(exception: unknown): number {
    if (exception instanceof HttpException) {
      return exception.getStatus();
    }

    if (exception instanceof Error) {
      if (exception.name === 'ValidationError') {
        return HttpStatus.BAD_REQUEST;
      }
    }

    return HttpStatus.INTERNAL_SERVER_ERROR;
  }

  private buildErrorResponse(
    exception: unknown,
    status: number,
    traceId: string,
  ): IErrorResponse {
    if (exception instanceof HttpException) {
      const response = exception.getResponse();

      if (typeof response === 'object' && response !== null) {
        const responseObj = response as Record<string, unknown>;

        if (responseObj.success === false && responseObj.error) {
          return response as unknown as IErrorResponse;
        }

        const message =
          typeof responseObj.message === 'string'
            ? responseObj.message
            : Array.isArray(responseObj.message)
              ? responseObj.message.join(', ')
              : exception.message;

        const details =
          Array.isArray(responseObj.message) &&
          typeof responseObj.message[0] === 'object'
            ? (
                responseObj.message as Array<{ field: string; message: string }>
              ).map((e) => ({
                field: e.field || 'unknown',
                message: typeof e === 'string' ? e : e.message,
              }))
            : undefined;

        return ErrorResponse.create(
          this.mapStatusToErrorCode(status),
          message,
          traceId,
          details,
        );
      }

      return ErrorResponse.create(
        this.mapStatusToErrorCode(status),
        typeof response === 'string' ? response : exception.message,
        traceId,
      );
    }

    if (exception instanceof Error) {
      const isProduction = process.env.NODE_ENV === 'production';
      return ErrorResponse.create(
        ErrorCode.INTERNAL_ERROR,
        isProduction ? 'Internal server error' : exception.message,
        traceId,
      );
    }

    return ErrorResponse.internalError(traceId);
  }

  private mapStatusToErrorCode(status: number): ErrorCode {
    const mapping: Record<number, ErrorCode> = {
      [HttpStatus.UNAUTHORIZED]: ErrorCode.UNAUTHORIZED,
      [HttpStatus.FORBIDDEN]: ErrorCode.FORBIDDEN,
      [HttpStatus.NOT_FOUND]: ErrorCode.NOT_FOUND,
      [HttpStatus.BAD_REQUEST]: ErrorCode.VALIDATION_ERROR,
      [HttpStatus.TOO_MANY_REQUESTS]: ErrorCode.RATE_LIMIT_EXCEEDED,
      [HttpStatus.SERVICE_UNAVAILABLE]: ErrorCode.SERVICE_UNAVAILABLE,
      [HttpStatus.BAD_GATEWAY]: ErrorCode.BAD_GATEWAY,
      [HttpStatus.GATEWAY_TIMEOUT]: ErrorCode.TIMEOUT,
    };

    return mapping[status] || ErrorCode.INTERNAL_ERROR;
  }
}
