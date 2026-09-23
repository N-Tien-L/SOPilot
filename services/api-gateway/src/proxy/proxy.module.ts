import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module';
import { ProxyService } from './proxy.service';
import { ProxyController } from './proxy.controller';
import { AuthProxyController } from '../auth/auth-proxy.controller';
import { RolesGuard } from '../common/guards';

@Module({
  imports: [AuthModule],
  controllers: [ProxyController, AuthProxyController],
  providers: [ProxyService, RolesGuard],
  exports: [ProxyService],
})
export class ProxyModule {}
