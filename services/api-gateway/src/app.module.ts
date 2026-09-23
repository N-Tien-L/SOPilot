import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import Joi from 'joi';
import { APP_FILTER, APP_INTERCEPTOR } from '@nestjs/core';
import { WinstonModule } from 'nest-winston';
import { createWinstonConfig } from './logging/winston.config';
import {
  appConfig,
  jwtConfig,
  corsConfig,
  servicesConfig,
  circuitBreakerConfig,
  loggingConfig,
  throttlerConfig,
  redisConfig,
  internalConfig,
} from './config';
import { AppController } from './app.controller';
import { AuthModule } from './auth';
import { ProxyModule } from './proxy';
import { HealthModule } from './health';
import { RolesGuard } from './common/guards';
import { HttpExceptionFilter } from './common/filters';
import {
  LoggingInterceptor,
  TraceIdInterceptor,
  ResponseTransformInterceptor,
  TimeoutInterceptor,
  RateLimitInterceptor,
} from './common/interceptors';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [
        appConfig,
        jwtConfig,
        corsConfig,
        servicesConfig,
        circuitBreakerConfig,
        loggingConfig,
        throttlerConfig,
        redisConfig,
        internalConfig,
      ],
      envFilePath: '.env',
      validationSchema: Joi.object({
        JWT_SECRET: Joi.string().min(32).required(),
        JWT_ISSUER: Joi.string().default('poliwise-auth-service'),
        REDIS_URL: Joi.string().uri().default('redis://localhost:6379'),
      }),
    }),
    WinstonModule.forRoot(createWinstonConfig()),
    AuthModule,
    ProxyModule,
    HealthModule,
  ],
  controllers: [AppController],
  providers: [
    {
      provide: APP_FILTER,
      useClass: HttpExceptionFilter,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: TraceIdInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: LoggingInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: ResponseTransformInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: TimeoutInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: RateLimitInterceptor,
    },
    RolesGuard,
  ],
})
export class AppModule {}
