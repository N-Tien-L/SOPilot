import { NestFactory } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import { AppModule } from './app.module';
import helmet from 'helmet';
import compression from 'compression';
import cookieParser from 'cookie-parser';
import { Logger, ValidationPipe } from '@nestjs/common';
import { HttpExceptionFilter } from './common/filters';

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule, {
    bufferLogs: true,
  });

  const configService = app.get(ConfigService);
  const port = configService.get<number>('app.port') || 3000;
  const nodeEnv = configService.get<string>('app.nodeEnv') || 'development';

  app.use(helmet());
  app.use(cookieParser()); // Phase 2: Google OAuth state cookie
  app.use(
    compression({
      filter: (req, res) => {
        const contentType = res.getHeader('content-type');
        if (contentType && String(contentType).includes('text/event-stream')) {
          return false;
        }
        return compression.filter(req, res);
      },
    }),
  );

  app.enableCors({
    origin: configService.get<string>('cors.origin') || 'http://localhost:3000',
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: [
      'Content-Type',
      'Authorization',
      'X-Trace-ID',
      'X-Requested-With',
      'X-Forwarded-For',
      'X-Real-IP',
      'X-User-Id',
      'X-User-ID',
      'X-BYOK-Key',
      'X-BYOK-Provider',
      'X-Internal-Provider-Key',
      'X-Internal-Provider',
      'X-Identity-Kind',
      'X-Workspace-Id',
    ],
    maxAge: 86400,
  });

  app.useGlobalFilters(new HttpExceptionFilter());

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: {
        enableImplicitConversion: true,
      },
    }),
  );

  app.enableShutdownHooks();

  await app.listen(port, '0.0.0.0');

  logger.log(`API Gateway is running on 0.0.0.0:${port}`);
  logger.log(`Environment: ${nodeEnv}`);
  logger.log(`CORS origin: ${configService.get<string>('cors.origin')}`);
}

bootstrap();
