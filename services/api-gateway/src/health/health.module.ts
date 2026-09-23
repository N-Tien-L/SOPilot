import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
import { ServicesIndicator } from './indicators/services.indicator';
import { MetricsService } from './metrics/metrics.service';
import { ProxyModule } from '../proxy/proxy.module';

@Module({
  imports: [ProxyModule],
  controllers: [HealthController],
  providers: [ServicesIndicator, MetricsService],
  exports: [MetricsService],
})
export class HealthModule {}
