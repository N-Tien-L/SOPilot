import { Controller, Get, Query, DefaultValuePipe, ParseIntPipe } from '@nestjs/common';
import { ServicesIndicator } from './indicators/services.indicator';
import { MetricsService, DailyErrorCount } from './metrics/metrics.service';
import { ApiResponse } from '../common/dto';
import { Public } from '../common/decorators';
import { ProxyService, ServiceName } from '../proxy/proxy.service';

@Controller('health')
export class HealthController {
  constructor(
    private readonly servicesIndicator: ServicesIndicator,
    private readonly metricsService: MetricsService,
    private readonly proxyService: ProxyService,
  ) {}

  @Get()
  @Public()
  async check() {
    return ApiResponse.success({
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'api-gateway',
    });
  }

  @Get('live')
  @Public()
  async live() {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
    };
  }

  @Get('ready')
  @Public()
  async ready() {
    const services = await this.servicesIndicator.checkAllServices();
    const allUp = services.every((s) => s.status === 'up');

    return ApiResponse.success({
      status: allUp ? 'ready' : 'degraded',
      timestamp: new Date().toISOString(),
      services,
    });
  }

  @Get('circuit-breakers')
  @Public()
  async circuitBreakers() {
    const statuses = Object.values(ServiceName).map((service) =>
      this.proxyService.getCircuitBreakerStatus(service),
    );

    return ApiResponse.success({
      timestamp: new Date().toISOString(),
      circuitBreakers: statuses,
    });
  }

  @Get('api-metrics')
  async getApiMetrics(
    @Query('days', new DefaultValuePipe(7), ParseIntPipe) days: number,
  ): Promise<ApiResponse<{
    timestamp: string;
    overall: { totalRequests: number; totalErrors: number; successRate: number };
    endpoints: Array<{
      path: string; total: number; success: number; failure: number;
      avgResponseTime: number;
      recentErrors: Array<{ timestamp: string; method: string; statusCode: number; path: string }>;
    }>;
    dailyErrors: DailyErrorCount[];
    services: Array<{ service: string; status: string; responseTime?: number }>;
  }>> {
    const metrics = this.metricsService.getMetrics(days);
    const services = await this.servicesIndicator.checkAllServices();

    const overall = {
      totalRequests: metrics.totalRequests,
      totalErrors: metrics.totalErrors,
      successRate:
        metrics.totalRequests > 0
          ? Math.round(
              ((metrics.totalRequests - metrics.totalErrors) /
                metrics.totalRequests) *
                100,
            )
          : 100,
    };

    const endpoints = Object.entries(metrics.endpointMetrics).map(
      ([path, m]) => ({
        path,
        total: m.total,
        success: m.success,
        failure: m.failure,
        avgResponseTime: m.avgResponseTime,
        recentErrors: m.recentErrors,
      }),
    );

    return ApiResponse.success({
      timestamp: new Date().toISOString(),
      overall,
      endpoints,
      dailyErrors: metrics.dailyErrors,
      services,
    });
  }
}
