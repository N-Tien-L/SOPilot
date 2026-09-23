import { Injectable, Logger, OnModuleInit } from '@nestjs/common';

interface EndpointMetrics {
  total: number;
  success: number;
  failure: number;
  avgResponseTime: number;
  recentErrors: Array<{
    timestamp: string;
    method: string;
    statusCode: number;
    path: string;
  }>;
}

export interface DailyErrorCount {
  date: string;
  errors: number;
}

interface MetricsSnapshot {
  endpointMetrics: Record<string, EndpointMetrics>;
  totalRequests: number;
  totalErrors: number;
  dailyErrors: DailyErrorCount[];
}

@Injectable()
export class MetricsService implements OnModuleInit {
  private readonly logger = new Logger(MetricsService.name);

  private readonly endpointMetrics = new Map<string, EndpointMetrics>();
  private readonly dailyErrors: Map<string, number> = new Map();

  private cleanupHandle: ReturnType<typeof setInterval>;

  onModuleInit() {
    this.cleanupHandle = setInterval(() => this.cleanupOldData(), 60 * 60 * 1000);
    this.logger.log('MetricsService initialized');
  }

  onDestroy() {
    clearInterval(this.cleanupHandle);
  }

  recordRequest(params: {
    method: string;
    path: string;
    statusCode: number;
    duration: number;
    userId: string;
    traceId: string;
  }) {
    const { method, path, statusCode, duration } = params;
    const normalizedPath = this.normalizePath(path);
    const isError = statusCode >= 400;

    let metrics = this.endpointMetrics.get(normalizedPath);
    if (!metrics) {
      metrics = {
        total: 0,
        success: 0,
        failure: 0,
        avgResponseTime: 0,
        recentErrors: [],
      };
      this.endpointMetrics.set(normalizedPath, metrics);
    }

    metrics.total++;
    if (isError) {
      metrics.failure++;
      this.incrementDailyError();

      if (metrics.recentErrors.length >= 5) {
        metrics.recentErrors.shift();
      }
      metrics.recentErrors.push({
        timestamp: new Date().toISOString(),
        method,
        statusCode,
        path: normalizedPath,
      });
    } else {
      metrics.success++;
    }

    const totalTime = metrics.avgResponseTime * (metrics.total - 1);
    metrics.avgResponseTime = Math.round((totalTime + duration) / metrics.total);
  }

  private normalizePath(path: string): string {
    let normalized = path;
    if (!normalized.startsWith('/api/v1')) {
      normalized = '/api/v1' + normalized;
    }
    return normalized
      .replace(/\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '/:id')
      .replace(/\/\d+/g, '/:id');
  }

  private incrementDailyError() {
    const today = new Date().toISOString().split('T')[0];
    this.dailyErrors.set(today, (this.dailyErrors.get(today) || 0) + 1);
  }

  getMetrics(days = 7): MetricsSnapshot {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().split('T')[0];

    const dailyErrors: DailyErrorCount[] = [];
    for (const [date, count] of this.dailyErrors.entries()) {
      if (date >= cutoffStr) {
        dailyErrors.push({ date, errors: count });
      }
    }
    dailyErrors.sort((a, b) => a.date.localeCompare(b.date));

    const endpointMetrics: Record<string, EndpointMetrics> = {};
    let totalRequests = 0;
    let totalErrors = 0;

    for (const [path, metrics] of this.endpointMetrics.entries()) {
      endpointMetrics[path] = { ...metrics };
      totalRequests += metrics.total;
      totalErrors += metrics.failure;
    }

    return {
      endpointMetrics,
      totalRequests,
      totalErrors,
      dailyErrors,
    };
  }

  private cleanupOldData() {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    const cutoffStr = cutoff.toISOString().split('T')[0];

    for (const date of this.dailyErrors.keys()) {
      if (date < cutoffStr) {
        this.dailyErrors.delete(date);
      }
    }

    for (const [path, metrics] of this.endpointMetrics.entries()) {
      if (metrics.total === 0) {
        this.endpointMetrics.delete(path);
      } else {
        const recent = metrics.recentErrors.filter(
          (e) => e.timestamp.split('T')[0] >= cutoffStr,
        );
        (metrics as any).recentErrors = recent;
      }
    }

    this.logger.debug('Metrics cleanup completed');
  }
}
