export enum ErrorCode {
  UNAUTHORIZED = 'UNAUTHORIZED',
  ACCOUNT_DEACTIVATED = 'ACCOUNT_DEACTIVATED',
  ACCOUNT_REVOKED = 'ACCOUNT_REVOKED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  BAD_GATEWAY = 'BAD_GATEWAY',
  TIMEOUT = 'TIMEOUT',
}

export interface IValidationError {
  field: string;
  message: string;
}

export interface IErrorResponse {
  success: false;
  error: {
    code: ErrorCode;
    message: string;
    details?: IValidationError[];
    retryAfter?: number;
  };
  timestamp: string;
  traceId?: string;
}

export class ErrorResponse {
  static create(
    code: ErrorCode,
    message: string,
    traceId?: string,
    details?: IValidationError[],
    retryAfter?: number,
  ): IErrorResponse {
    return {
      success: false,
      error: {
        code,
        message,
        ...(details && { details }),
        ...(retryAfter !== undefined && { retryAfter }),
      },
      timestamp: new Date().toISOString(),
      traceId,
    };
  }

  static unauthorized(
    message = 'Unauthorized access',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.UNAUTHORIZED, message, traceId);
  }

  static forbidden(
    message = 'Insufficient permissions',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.FORBIDDEN, message, traceId);
  }

  static accountDeactivated(traceId?: string): IErrorResponse {
    return this.create(
      ErrorCode.ACCOUNT_DEACTIVATED,
      'Account has been deactivated. Please contact administrator.',
      traceId,
    );
  }

  static accountRevoked(traceId?: string): IErrorResponse {
    return this.create(
      ErrorCode.ACCOUNT_REVOKED,
      'Account has been revoked. Access denied.',
      traceId,
    );
  }

  static notFound(
    message = 'Resource not found',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.NOT_FOUND, message, traceId);
  }

  static validationError(
    details: IValidationError[],
    message = 'Validation failed',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.VALIDATION_ERROR, message, traceId, details);
  }

  static rateLimitExceeded(
    retryAfter: number,
    traceId?: string,
  ): IErrorResponse {
    return this.create(
      ErrorCode.RATE_LIMIT_EXCEEDED,
      'Too many requests. Please try again later.',
      traceId,
      undefined,
      retryAfter,
    );
  }

  static serviceUnavailable(retryAfter = 30, traceId?: string): IErrorResponse {
    return this.create(
      ErrorCode.SERVICE_UNAVAILABLE,
      'Service temporarily unavailable. Please try again later.',
      traceId,
      undefined,
      retryAfter,
    );
  }

  static internalError(
    message = 'Internal server error',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.INTERNAL_ERROR, message, traceId);
  }

  static badGateway(
    message = 'Downstream service error',
    traceId?: string,
  ): IErrorResponse {
    return this.create(ErrorCode.BAD_GATEWAY, message, traceId);
  }
}
