import {
  Controller,
  Post,
  Get,
  Put,
  Delete,
  Patch,
  Req,
  HttpCode,
  HttpStatus,
  Logger,
  UseGuards,
  Param,
  Body,
} from '@nestjs/common';
import type { Request } from 'express';
import { ProxyService, ServiceName } from '../proxy/proxy.service';
import { Public } from '../common/decorators';
import { JwtAuthGuard } from '../common/guards';
import { Roles } from '../common/decorators/roles.decorator';
import { UserRole } from '../common/interfaces/jwt-payload.interface';

@Controller('api/v1/auth')
export class AuthProxyController {
  private readonly logger = new Logger(AuthProxyController.name);

  constructor(private readonly proxyService: ProxyService) {}

  @Public()
  @Post('login')
  @HttpCode(HttpStatus.OK)
  handleLogin(@Req() request: Request) {
    this.logger.debug(`Login request body: ${JSON.stringify(request.body)}`);
    const path = '/api/v1/auth/login';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('register')
  @HttpCode(HttpStatus.CREATED)
  handleRegister(@Req() request: Request) {
    const path = '/api/v1/auth/register';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  handleRefresh(@Req() request: Request) {
    const path = '/api/v1/auth/refresh';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('forgot-password')
  @HttpCode(HttpStatus.OK)
  handleForgotPassword(@Req() request: Request) {
    const path = '/api/v1/auth/forgot-password';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('send-otp')
  @HttpCode(HttpStatus.OK)
  handleSendOtp(@Req() request: Request) {
    const path = '/api/v1/auth/send-otp';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('verify-otp')
  @HttpCode(HttpStatus.OK)
  handleVerifyOtp(@Req() request: Request) {
    const path = '/api/v1/auth/verify-otp';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @Public()
  @Post('reset-password')
  @HttpCode(HttpStatus.OK)
  handleResetPassword(@Req() request: Request) {
    const path = '/api/v1/auth/reset-password';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Post('logout')
  @HttpCode(HttpStatus.OK)
  handleLogout(@Req() request: Request) {
    const path = '/api/v1/auth/logout';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Post('logout-all')
  @HttpCode(HttpStatus.OK)
  handleLogoutAll(@Req() request: Request) {
    const path = '/api/v1/auth/logout-all';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Get('sessions')
  handleGetSessions(@Req() request: Request) {
    const path = '/api/v1/auth/sessions';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Delete('sessions/:sessionId')
  @HttpCode(HttpStatus.OK)
  handleRevokeSession(@Req() request: Request) {
    const sessionId = request.params.sessionId;
    const path = `/api/v1/auth/sessions/${sessionId}`;
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Post('change-password')
  @HttpCode(HttpStatus.OK)
  handleChangePassword(@Req() request: Request) {
    const path = '/api/v1/auth/change-password';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }

  @UseGuards(JwtAuthGuard)
  @Get('me')
  handleGetProfile(@Req() request: Request) {
    const path = '/api/v1/auth/me';
    return this.proxyService.forward(ServiceName.AUTH, request, path);
  }
}
