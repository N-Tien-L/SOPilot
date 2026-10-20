import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import request from 'supertest';
import type { Request } from 'express';
import { of } from 'rxjs';
import { AuthProxyController } from './auth-proxy.controller';
import { ProxyService, ServiceName } from '../proxy/proxy.service';
import { JwtAuthService } from './services/jwt-auth.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { IS_PUBLIC_KEY } from '../common/decorators/public.decorator';

describe('AuthProxyController', () => {
  let controller: AuthProxyController;
  let reflector: Reflector;
  let proxyService: jest.Mocked<ProxyService>;
  let app: INestApplication;

  const testSecret = 'test-jwt-secret-key-for-gateway-tests';
  const testIssuer = 'poliwise-auth-service';

  beforeEach(async () => {
    const mockProxyService = {
      forward: jest.fn().mockImplementation(() => {
        return of({
          _proxied: true,
          data: {
            accessToken: 'mock-access-token',
            refreshToken: 'mock-refresh-token',
            user: { email: 'user@company.com', role: 'USER' },
          },
          statusCode: 200,
          headers: {},
        });
      }),
    };

    const mockConfigService = {
      getOrThrow: jest.fn((key: string) => {
        const config: Record<string, string> = {
          'jwt.secret': testSecret,
          'jwt.issuer': testIssuer,
        };
        return config[key];
      }),
      get: jest.fn((key: string) => {
        const config: Record<string, string> = {
          'jwt.secret': testSecret,
          'jwt.issuer': testIssuer,
        };
        return config[key];
      }),
    };

    const module: TestingModule = await Test.createTestingModule({
      controllers: [AuthProxyController],
      providers: [
        Reflector,
        JwtAuthGuard,
        JwtAuthService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
        {
          provide: ProxyService,
          useValue: mockProxyService,
        },
      ],
    }).compile();

    controller = module.get<AuthProxyController>(AuthProxyController);
    reflector = module.get<Reflector>(Reflector);
    proxyService = module.get(ProxyService);

    app = module.createNestApplication();
    await app.init();
  });

  afterEach(async () => {
    if (app) {
      await app.close();
    }
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });

  describe('handleGoogleVerify', () => {
    it('should be marked with @Public decorator', () => {
      const isPublic = reflector.get<boolean>(
        IS_PUBLIC_KEY,
        controller.handleGoogleVerify,
      );
      expect(isPublic).toBe(true);
    });

    it('should forward request to auth-service at /api/v1/auth/google/verify', () => {
      const mockRequest = {
        method: 'POST',
        headers: {},
        body: { idToken: 'google-id-token-xyz' },
      } as unknown as Request;

      const mockResponse = {
        _proxied: true,
        data: {
          accessToken: 'jwt-access-token',
          user: { email: 'user@company.com' },
        },
        statusCode: 200,
      };

      proxyService.forward.mockReturnValue(of(mockResponse));

      const result = controller.handleGoogleVerify(mockRequest);

      expect(proxyService.forward).toHaveBeenCalledTimes(1);
      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.AUTH,
        mockRequest,
        '/api/v1/auth/google/verify',
      );
      expect(result).toBeDefined();
    });

    it('should allow public access via HTTP POST without Authorization header', async () => {
      await request(app.getHttpServer())
        .post('/api/v1/auth/google/verify')
        .send({ idToken: 'google-id-token-xyz' })
        .expect(200);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.AUTH,
        expect.anything(),
        '/api/v1/auth/google/verify',
      );
    });
  });
});
