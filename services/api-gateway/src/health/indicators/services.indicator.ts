import { Injectable } from '@nestjs/common';
import { ProxyService, ServiceName } from '../../proxy/proxy.service';

export interface ServiceHealth {
  service: string;
  status: 'up' | 'down' | 'unknown';
  responseTime?: number;
}

@Injectable()
export class ServicesIndicator {
  constructor(private readonly proxyService: ProxyService) {}

  async isHealthy(service: ServiceName): Promise<ServiceHealth> {
    const serviceNames: Record<ServiceName, string> = {
      [ServiceName.AUTH]: 'Auth Service',
      [ServiceName.USER]: 'User Service',
      [ServiceName.KNOWLEDGE]: 'Knowledge Service',
      [ServiceName.METADATA]: 'Metadata Service',
      [ServiceName.FEEDBACK]: 'Feedback Service',
      [ServiceName.AI_QA]: 'AI QA Service',
      [ServiceName.INGESTION]: 'Ingestion Service',
    };

    const startTime = Date.now();

    try {
      const isUp = await this.proxyService.getServiceHealth(service);
      const responseTime = Date.now() - startTime;

      return {
        service: serviceNames[service],
        status: isUp ? 'up' : 'down',
        responseTime,
      };
    } catch {
      return {
        service: serviceNames[service],
        status: 'down',
      };
    }
  }

  async checkAllServices(): Promise<ServiceHealth[]> {
    const checks = await Promise.all([
      this.isHealthy(ServiceName.AUTH),
      this.isHealthy(ServiceName.USER),
      this.isHealthy(ServiceName.KNOWLEDGE),
      this.isHealthy(ServiceName.METADATA),
      this.isHealthy(ServiceName.FEEDBACK),
    ]);

    return checks;
  }
}
