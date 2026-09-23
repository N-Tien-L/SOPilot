import { registerAs } from '@nestjs/config';

export const appConfig = registerAs('app', () => ({
  port: parseInt(process.env.PORT || '3000', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  isProduction: process.env.NODE_ENV === 'production',
  isDevelopment: process.env.NODE_ENV === 'development',
}));

export const jwtConfig = registerAs('jwt', () => ({
  secret: process.env.JWT_SECRET,
  issuer: process.env.JWT_ISSUER || 'poliwise-auth-service',
}));

export const corsConfig = registerAs('cors', () => ({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true,
}));

export const servicesConfig = registerAs('services', () => ({
  auth: process.env.AUTH_SERVICE_URL || 'http://localhost:8081',
  user: process.env.USER_SERVICE_URL || 'http://localhost:8082',
  knowledge: process.env.KNOWLEDGE_SERVICE_URL || 'http://localhost:8083',
  metadata: process.env.METADATA_SERVICE_URL || 'http://localhost:8084',
  feedback: process.env.FEEDBACK_SERVICE_URL || 'http://localhost:8085',
  aiQa: process.env.AI_QA_SERVICE_URL || 'http://localhost:8086',
  ingestion: process.env.INGESTION_SERVICE_URL || 'http://localhost:8088',
}));

export const throttlerConfig = registerAs('throttler', () => ({
  ttl: parseInt(process.env.THROTTLE_TTL || '60000', 10),
  limits: {
    user: parseInt(process.env.THROTTLE_LIMIT_USER || '100', 10),
    manager: parseInt(process.env.THROTTLE_LIMIT_MANAGER || '200', 10),
    admin: parseInt(process.env.THROTTLE_LIMIT_ADMIN || '500', 10),
    public: parseInt(process.env.THROTTLE_LIMIT_PUBLIC || '20', 10),
  },
}));

export const redisConfig = registerAs('redis', () => ({
  url: process.env.REDIS_URL || 'redis://localhost:6379',
  port: parseInt(process.env.REDIS_PORT || '6379', 10),
  password: process.env.REDIS_PASSWORD || undefined,
  ttl: parseInt(process.env.REDIS_TTL || '60000', 10),
}));

export const circuitBreakerConfig = registerAs('circuitBreaker', () => ({
  timeout: parseInt(process.env.CIRCUIT_BREAKER_TIMEOUT || '30000', 10),
  volumeThreshold: parseInt(
    process.env.CIRCUIT_BREAKER_VOLUME_THRESHOLD || '10',
    10,
  ),
  errorPercentageThreshold: 50,
  resetTimeout: 30000,
}));

export const loggingConfig = registerAs('logging', () => ({
  level: process.env.LOG_LEVEL || 'info',
  isProduction: process.env.NODE_ENV === 'production',
}));

export const oauthConfig = registerAs('oauth', () => ({
  google: {
    clientId: process.env.GOOGLE_OAUTH_CLIENT_ID || '',
    clientSecret: process.env.GOOGLE_OAUTH_CLIENT_SECRET || '',
    redirectUri:
      process.env.GOOGLE_OAUTH_REDIRECT_URI ||
      'http://localhost:3001/auth/google/callback',
  },
}));

export const internalConfig = registerAs('internal', () => ({
  serviceToken: process.env.INTERNAL_SERVICE_TOKEN || '',
}));
