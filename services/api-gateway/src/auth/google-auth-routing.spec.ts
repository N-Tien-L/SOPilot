import { Test } from '@nestjs/testing';
import { ConfigModule } from '@nestjs/config';
import type { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { of } from 'rxjs';
import { AuthModule } from './auth.module';
import { AuthProxyController } from './auth-proxy.controller';
import { ProxyService } from '../proxy/proxy.service';

describe('Google auth route ownership', () => {
  let app: INestApplication;
  const proxy = { forward: jest.fn(() => of({ verifiedBy: 'auth-service' })) };

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({
              jwt: {
                secret: 'test-only-gateway-signing-key-minimum-32-chars',
                issuer: 'test',
              },
            }),
          ],
        }),
        AuthModule,
      ],
      controllers: [AuthProxyController],
      providers: [{ provide: ProxyService, useValue: proxy }],
    }).compile();
    app = module.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app?.close();
  });

  it('should forward the supported ID-token route to auth-service', async () => {
    // Arrange / Act
    const response = await request(app.getHttpServer())
      .post('/api/v1/auth/google/verify')
      .send({ idToken: 'test-token' });
    // Assert
    expect(response.status).toBe(200);
    expect(response.body.verifiedBy).toBe('auth-service');
    expect(proxy.forward).toHaveBeenCalled();
  });

  it('should expose no legacy Google code login endpoint', async () => {
    // Arrange / Act
    const response = await request(app.getHttpServer()).get(
      '/auth/google/login',
    );
    // Assert
    expect(response.status).toBe(404);
  });

  it('should expose no legacy Google code callback endpoint', async () => {
    // Arrange / Act
    const response = await request(app.getHttpServer()).get(
      '/auth/google/callback?code=test&state=test',
    );
    // Assert
    expect(response.status).toBe(404);
  });
});
