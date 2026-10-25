import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { Observable, from, throwError, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import CircuitBreaker from 'opossum';
import type { Request } from 'express';
import { TRACE_ID_HEADER } from '../common/utils';
import { ErrorResponse } from '../common/dto';
import { IUserContext } from '../common/interfaces';

export enum ServiceName {
  AUTH = 'auth',
  USER = 'user',
  KNOWLEDGE = 'knowledge',
  METADATA = 'metadata',
  FEEDBACK = 'feedback',
  AI_QA = 'ai_qa',
  INGESTION = 'ingestion',
}

interface ServiceEndpoint {
  name: string;
  baseUrl: string;
  timeout: number;
}

export function isUntrustedIdentityHeader(headerName: string): boolean {
  const normalized = headerName.toLowerCase();
  return (
    normalized === 'x-role' ||
    normalized === 'x-service-token' ||
    normalized.startsWith('x-user-') ||
    normalized.startsWith('x-department-') ||
    (normalized.startsWith('x-internal-') &&
      normalized !== 'x-internal-provider-key' &&
      normalized !== 'x-internal-provider')
  );
}

@Injectable()
export class ProxyService {
  private readonly logger = new Logger(ProxyService.name);
  private readonly axiosInstance: AxiosInstance;
  private readonly circuitBreakers: Map<ServiceName, CircuitBreaker>;
  private readonly services: Record<ServiceName, ServiceEndpoint>;

  constructor(private readonly configService: ConfigService) {
    this.services = {
      [ServiceName.AUTH]: {
        name: 'auth-service',
        baseUrl:
          this.configService.get<string>('services.auth') ||
          'http://localhost:8081',
        timeout: 30000,
      },
      [ServiceName.USER]: {
        name: 'user-service',
        baseUrl:
          this.configService.get<string>('services.user') ||
          'http://localhost:8082',
        timeout: 30000,
      },
      [ServiceName.KNOWLEDGE]: {
        name: 'knowledge-service',
        baseUrl:
          this.configService.get<string>('services.knowledge') ||
          'http://localhost:8083',
        timeout: 60000,
      },
      [ServiceName.METADATA]: {
        name: 'metadata-service',
        baseUrl:
          this.configService.get<string>('services.metadata') ||
          'http://localhost:8084',
        timeout: 30000,
      },
      [ServiceName.FEEDBACK]: {
        name: 'feedback-service',
        baseUrl:
          this.configService.get<string>('services.feedback') ||
          'http://localhost:8085',
        timeout: 30000,
      },
      [ServiceName.AI_QA]: {
        name: 'ai-qa-service',
        baseUrl:
          this.configService.get<string>('services.aiQa') ||
          'http://localhost:8086',
        timeout: 120000, // longer for LLM generation and streaming
      },
      [ServiceName.INGESTION]: {
        name: 'ingestion-service',
        baseUrl:
          this.configService.get<string>('services.ingestion') ||
          'http://localhost:8088',
        timeout: 60000, // longer for file processing
      },
    };

    this.axiosInstance = axios.create({
      timeout: 30000,
    });

    this.circuitBreakers = new Map();
    this.initializeCircuitBreakers();
  }

  private initializeCircuitBreakers() {
    const timeout =
      this.configService.get<number>('circuitBreaker.timeout') || 30000;
    const volumeThreshold =
      this.configService.get<number>('circuitBreaker.volumeThreshold') || 10;
    const errorPercentageThreshold =
      this.configService.get<number>(
        'circuitBreaker.errorPercentageThreshold',
      ) || 50;

    for (const serviceName of Object.values(ServiceName)) {
      const options: CircuitBreaker.Options = {
        timeout,
        errorThresholdPercentage: errorPercentageThreshold,
        volumeThreshold,
        resetTimeout: timeout,
      };

      const breaker = new CircuitBreaker(
        this.forwardRequest.bind(this),
        options,
      );

      breaker.on('open', () => {
        this.logger.warn(`Circuit breaker OPENED for ${serviceName}`);
      });

      breaker.on('close', () => {
        this.logger.log(`Circuit breaker CLOSED for ${serviceName}`);
      });

      breaker.on('halfOpen', () => {
        this.logger.log(`Circuit breaker HALF-OPEN for ${serviceName}`);
      });

      breaker.on('fallback', () => {
        this.logger.warn(
          `Circuit breaker fallback triggered for ${serviceName}`,
        );
      });

      breaker.on('success', () => {
        this.logger.debug(`Circuit breaker success for ${serviceName}`);
      });

      breaker.on('failure', () => {
        this.logger.error(`Circuit breaker failure for ${serviceName}`);
      });

      breaker.on('timeout', () => {
        this.logger.warn(`Circuit breaker timeout for ${serviceName}`);
      });

      this.circuitBreakers.set(serviceName, breaker);
    }
  }

  private async forwardRequest(context: {
    method: string;
    url: string;
    headers: Record<string, string>;
    data?: unknown;
    params?: Record<string, string>;
    timeout: number;
    isStream?: boolean;
    isBinary?: boolean;
  }): Promise<unknown> {
    const authHeader =
      context.headers['authorization'] || context.headers['Authorization'];
    const hasAuth = !!authHeader;
    const sanitizedHeaders = this.redactSecrets({
      ...context.headers,
      authorization: hasAuth ? 'Bearer <redacted>' : undefined,
    });
    this.logger.debug(
      `[forwardRequest] Sending request to ${context.url} ` +
        `| Authorization: ${hasAuth ? 'Bearer <redacted>' : 'MISSING!'} ` +
        `| Headers: ${JSON.stringify(sanitizedHeaders).substring(0, 200)}`,
    );

    // Detect binary responses (download/preview/file endpoints) to prevent Axios from JSON-parsing them
    const isDownloadRequest =
      context.url.includes('/download') ||
      context.url.includes('/preview') ||
      context.url.includes('/file');
    let responseType: AxiosRequestConfig['responseType'] =
      isDownloadRequest || context.isBinary ? 'arraybuffer' : 'json';

    if (context.isStream) {
      responseType = 'stream';
    }
    const config: AxiosRequestConfig = {
      method: context.method as any,
      url: context.url,
      headers: context.headers,
      data: context.data,
      params: context.params,
      timeout: context.timeout,
      validateStatus: () => true,
      responseType,
    };

    try {
      const response = await this.axiosInstance.request(config);
      this.logger.debug(
        `Response from ${context.url}: status=${response.status}, ` +
          `auth-received=${response.headers['authorization'] ? '<redacted>' : 'none'}`,
      );

      // For binary streams/file downloads, pass data through without JSON wrapping.
      if (context.isBinary || isDownloadRequest) {
        return {
          _proxied: true,
          data: response.data,
          statusCode: response.status,
          headers: this.extractProxyHeaders(
            response.headers as Record<string, string>,
          ),
          isBinary: true,
        };
      }

      return {
        _proxied: true,
        data: response.data,
        statusCode: response.status,
        headers: this.extractProxyHeaders(
          response.headers as Record<string, string>,
        ),
      };
    } catch (error) {
      const axiosError = error as AxiosError;
      this.logger.error(
        `Service call failed: ${axiosError.message}`,
        axiosError.stack,
      );
      throw new Error(`Service call failed: ${axiosError.message}`);
    }
  }

  private getFallbackResponse(serviceName: string, traceId?: string) {
    return ErrorResponse.serviceUnavailable(30, traceId);
  }

  forward(
    service: ServiceName,
    request: Request,
    path: string,
    isStream = false,
    isBinary = false,
  ): Observable<unknown> {
    const serviceConfig = this.services[service];
    if (!serviceConfig) {
      return throwError(() => new Error(`Unknown service: ${service}`));
    }

    const targetUrl = `${serviceConfig.baseUrl}${path}`;
    const user = request.user as IUserContext | undefined;
    const traceId =
      (request.headers[TRACE_ID_HEADER.toLowerCase()] as string) || undefined;

    const contentType = (request.headers['content-type'] as string) || '';
    const isMultipart = contentType
      .toLowerCase()
      .includes('multipart/form-data');
    const headers = this.buildForwardHeaders(request, user, traceId);
    const method = request.method.toLowerCase();
    const data = ['post', 'put', 'patch'].includes(method)
      ? isMultipart
        ? request
        : request.body
      : undefined;
    const params = request.query as Record<string, string>;

    const context = {
      method: request.method,
      url: targetUrl,
      headers,
      data,
      params,
      timeout: isStream ? 0 : serviceConfig.timeout,
      isStream,
      isBinary,
    };

    const breaker = this.circuitBreakers.get(service);

    if (!breaker) {
      return this.executeDirectRequest(context);
    }

    return from(breaker.fire(context)).pipe(
      catchError((error) => {
        this.logger.error(
          `Circuit breaker error for ${service}: ${error.message}`,
        );
        return of(this.getFallbackResponse(serviceConfig.name, traceId));
      }),
    );
  }

  private executeDirectRequest(context: {
    method: string;
    url: string;
    headers: Record<string, string>;
    data?: unknown;
    params?: Record<string, string>;
    timeout: number;
    isStream?: boolean;
    isBinary?: boolean;
  }): Observable<unknown> {
    const isDownloadRequest =
      context.url.includes('/download') ||
      context.url.includes('/preview') ||
      context.url.includes('/file');

    let responseType: AxiosRequestConfig['responseType'] = isDownloadRequest
      ? 'arraybuffer'
      : 'json';

    if (context.isStream) {
      responseType = 'stream';
    }

    const config: AxiosRequestConfig = {
      method: context.method as any,
      url: context.url,
      headers: context.headers,
      data: context.data,
      params: context.params,
      timeout: context.timeout,
      validateStatus: () => true,
      responseType,
    };

    return from(this.axiosInstance.request(config)).pipe(
      map((response) => {
        const isBinaryResponse = context.isBinary || isDownloadRequest;
        return {
          _proxied: true,
          data: response.data,
          statusCode: response.status,
          headers: this.extractProxyHeaders(
            response.headers as Record<string, string>,
          ),
          isBinary: isBinaryResponse,
        };
      }),
      catchError((error: AxiosError) => {
        const traceId = context.headers[TRACE_ID_HEADER] || undefined;
        if (
          error.code === 'ECONNABORTED' ||
          error.message.includes('timeout')
        ) {
          return of(ErrorResponse.badGateway('Request timeout', traceId));
        }
        return of(ErrorResponse.badGateway(error.message, traceId));
      }),
    );
  }

  private buildForwardHeaders(
    request: Request,
    user: IUserContext | undefined,
    traceId?: string,
  ): Record<string, string> {
    // Do NOT hardcode Content-Type — preserve the original request's Content-Type
    // (e.g., multipart/form-data for file uploads must pass through unchanged)
    const headers: Record<string, string> = {
      'X-Forwarded-For': request.ip || request.socket.remoteAddress || '',
      'X-Forwarded-Proto': request.protocol,
      'X-Request-Start': Date.now().toString(),
    };

    const hopByHopHeaders = [
      'host',
      'connection',
      'keep-alive',
      'proxy-authenticate',
      'proxy-authorization',
      'te',
      'trailers',
      'transfer-encoding',
      'upgrade',
      'content-length',
    ];

    for (const [key, value] of Object.entries(request.headers)) {
      if (
        !hopByHopHeaders.includes(key.toLowerCase()) &&
        !isUntrustedIdentityHeader(key) &&
        value
      ) {
        const normalized = Array.isArray(value) ? value[0] : value;
        if (normalized && normalized !== 'undefined') {
          headers[key] = normalized;
        }
      }
    }

    if (traceId) {
      headers[TRACE_ID_HEADER] = traceId;
    }

    if (user) {
      headers['X-User-Id'] = user.userId;
      headers['X-Role'] = user.role;
      if (user.department) {
        headers['X-Department-Id'] = user.department;
      }
      // Phase 2: demo users carry their workspace identity downstream
      if (user.identityKind === 'demo') {
        headers['X-Identity-Kind'] = 'demo';
        headers['X-Workspace-Id'] = user.workspaceId ?? user.userId;
      }
    }

    return headers;
  }

  /**
   * Extract and normalize response headers from downstream service to forward to client.
   * Only forwards headers that are safe/proxy-relevant; skips hop-by-hop headers.
   */
  private extractProxyHeaders(
    downstreamHeaders: Record<string, string>,
  ): Record<string, string> {
    const hopByHopHeaders = [
      'transfer-encoding',
      'connection',
      'keep-alive',
      'proxy-authenticate',
      'proxy-authorization',
      'te',
      'trailers',
      'upgrade',
    ];
    const forwarded: Record<string, string> = {};
    for (const [key, value] of Object.entries(downstreamHeaders)) {
      if (!hopByHopHeaders.includes(key.toLowerCase()) && value !== undefined) {
        forwarded[key] = Array.isArray(value) ? value[0] : value;
      }
    }
    return forwarded;
  }

  private isStreamResponse(data: unknown): boolean {
    if (data === null || data === undefined) return false;
    const proto = Object.prototype.toString.call(data);
    // Node.js streams often have this proto or similar
    if (proto === '[object ReadableStream]' || proto === '[object Readable]')
      return true;
    // Check if it's a pipeable stream
    return typeof (data as any).pipe === 'function';
  }

  private redactSecrets(
    headers: Record<string, string | undefined>,
  ): Record<string, string | undefined> {
    const sensitiveKeys = new Set([
      'authorization',
      'x-byok-key',
      'x-internal-provider-key',
      'x-api-key',
      'x-internal-api-key',
      'x-service-token',
      'cookie',
      'set-cookie',
    ]);
    const result: Record<string, string | undefined> = {};
    for (const [key, value] of Object.entries(headers)) {
      if (sensitiveKeys.has(key.toLowerCase())) {
        result[key] = value ? '<redacted>' : value;
      } else {
        result[key] = value;
      }
    }
    return result;
  }

  getServiceHealth(service: ServiceName): Promise<boolean> {
    const serviceConfig = this.services[service];
    if (!serviceConfig) {
      return Promise.resolve(false);
    }

    return axios
      .get(`${serviceConfig.baseUrl}/actuator/health`, { timeout: 5000 })
      .then((res) => res.status === 200)
      .catch(() => false);
  }

  getCircuitBreakerStatus(service: ServiceName) {
    const breaker = this.circuitBreakers.get(service);
    if (!breaker) {
      return null;
    }

    return {
      service,
      name: this.services[service].name,
      status: breaker.status,
      stats: breaker.stats,
    };
  }
}
