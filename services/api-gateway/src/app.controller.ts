import { Controller, Get } from '@nestjs/common';
import { ApiResponse } from './common/dto';
import { Public } from './common/decorators';

@Controller()
export class AppController {
  @Get()
  @Public()
  getStatus() {
    return ApiResponse.success({
      service: 'api-gateway',
      version: '1.0.0',
      status: 'running',
      timestamp: new Date().toISOString(),
    });
  }
}
