import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ConfigService } from '@nestjs/config';
import request from 'supertest';
import { of } from 'rxjs';
import type { Request } from 'express';
import { ProxyController } from './proxy.controller';
import { ProxyService, ServiceName } from './proxy.service';
import { JwtAuthService } from '../auth/services/jwt-auth.service';
import { JwtAuthGuard, RolesGuard } from '../common/guards';
import { UserRole, AccountStatus } from '../common/interfaces';
import { ROLES_KEY } from '../common/decorators/roles.decorator';

describe('ProxyController - Employee Roster Routes', () => {
  let controller: ProxyController;
  let reflector: Reflector;
  let proxyService: jest.Mocked<ProxyService>;
  let jwtAuthService: JwtAuthService;
  let app: INestApplication;

  const testSecret = 'test-jwt-secret-key-for-gateway-tests';
  const testIssuer = 'poliwise-auth-service';

  let adminToken: string;
  let managerToken: string;
  let userToken: string;

  beforeEach(async () => {
    const mockProxyService = {
      forward: jest
        .fn()
        .mockImplementation((service, _req, path, _isStream, isBinary) => {
          if (isBinary) {
            return of({
              _proxied: true,
              data: Buffer.from('fake-excel-content'),
              statusCode: 200,
              headers: {
                'content-type':
                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'content-disposition':
                  'attachment; filename="employee_roster_template.xlsx"',
              },
              isBinary: true,
            });
          }
          return of({
            _proxied: true,
            data: { success: true, path, service },
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
      controllers: [ProxyController],
      providers: [
        Reflector,
        JwtAuthGuard,
        RolesGuard,
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

    controller = module.get<ProxyController>(ProxyController);
    reflector = module.get<Reflector>(Reflector);
    proxyService = module.get(ProxyService);
    jwtAuthService = module.get<JwtAuthService>(JwtAuthService);

    adminToken = jwtAuthService.sign({
      sub: 'admin-1',
      username: 'admin',
      email: 'admin@company.com',
      role: UserRole.ADMIN,
      status: AccountStatus.ACTIVE,
    });

    managerToken = jwtAuthService.sign({
      sub: 'manager-1',
      username: 'manager',
      email: 'manager@company.com',
      role: UserRole.MANAGER,
      status: AccountStatus.ACTIVE,
    });

    userToken = jwtAuthService.sign({
      sub: 'user-1',
      username: 'user',
      email: 'user@company.com',
      role: UserRole.USER,
      status: AccountStatus.ACTIVE,
    });

    app = module.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true }));
    await app.init();
  });

  afterEach(async () => {
    if (app) {
      await app.close();
    }
  });

  describe('Unit: Method signatures and metadata', () => {
    it('handleRosterTemplateDownload has ADMIN and MANAGER roles and sets isBinary=true', () => {
      const roles = reflector.get<UserRole[]>(
        ROLES_KEY,
        controller.handleRosterTemplateDownload,
      );
      expect(roles).toEqual([UserRole.ADMIN, UserRole.MANAGER]);

      const mockReq = {
        path: '/api/v1/users/roster/template',
      } as unknown as Request;
      controller.handleRosterTemplateDownload(mockReq);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.USER,
        mockReq,
        '/api/v1/users/roster/template',
        false,
        true,
      );
    });

    it('handleRosterImport has ADMIN role and forwards to user-service', () => {
      const roles = reflector.get<UserRole[]>(
        ROLES_KEY,
        controller.handleRosterImport,
      );
      expect(roles).toEqual([UserRole.ADMIN]);

      const mockReq = {
        path: '/api/v1/users/roster/import',
      } as unknown as Request;
      controller.handleRosterImport(mockReq);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.USER,
        mockReq,
        '/api/v1/users/roster/import',
      );
    });

    it('handleRosterList has ADMIN role and forwards to user-service', () => {
      const roles = reflector.get<UserRole[]>(
        ROLES_KEY,
        controller.handleRosterList,
      );
      expect(roles).toEqual([UserRole.ADMIN]);

      const mockReq = {
        path: '/api/v1/users/roster',
      } as unknown as Request;
      controller.handleRosterList(mockReq);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.USER,
        mockReq,
        '/api/v1/users/roster',
      );
    });

    it('handleRosterGetById has ADMIN role and forwards to user-service', () => {
      const roles = reflector.get<UserRole[]>(
        ROLES_KEY,
        controller.handleRosterGetById,
      );
      expect(roles).toEqual([UserRole.ADMIN]);

      const mockReq = {
        path: '/api/v1/users/roster/uuid-123',
      } as unknown as Request;
      controller.handleRosterGetById(mockReq);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.USER,
        mockReq,
        '/api/v1/users/roster/uuid-123',
      );
    });

    it('handleRosterDelete has ADMIN role and forwards to user-service', () => {
      const roles = reflector.get<UserRole[]>(
        ROLES_KEY,
        controller.handleRosterDelete,
      );
      expect(roles).toEqual([UserRole.ADMIN]);

      const mockReq = {
        path: '/api/v1/users/roster/uuid-123',
      } as unknown as Request;
      controller.handleRosterDelete(mockReq);

      expect(proxyService.forward).toHaveBeenCalledWith(
        ServiceName.USER,
        mockReq,
        '/api/v1/users/roster/uuid-123',
      );
    });
  });

  describe('Integration (HTTP Routing & Authorization)', () => {
    describe('Authentication (401 when token missing)', () => {
      it('GET /api/v1/users/roster/template requires auth', async () => {
        await request(app.getHttpServer())
          .get('/api/v1/users/roster/template')
          .expect(401);
      });

      it('POST /api/v1/users/roster/import requires auth', async () => {
        await request(app.getHttpServer())
          .post('/api/v1/users/roster/import')
          .expect(401);
      });

      it('GET /api/v1/users/roster requires auth', async () => {
        await request(app.getHttpServer())
          .get('/api/v1/users/roster')
          .expect(401);
      });

      it('DELETE /api/v1/users/roster/uuid-123 requires auth', async () => {
        await request(app.getHttpServer())
          .delete('/api/v1/users/roster/uuid-123')
          .expect(401);
      });
    });

    describe('Role-Based Access Control', () => {
      it('USER role is forbidden (403) from accessing roster endpoints', async () => {
        await request(app.getHttpServer())
          .get('/api/v1/users/roster/template')
          .set('Authorization', `Bearer ${userToken}`)
          .expect(403);

        await request(app.getHttpServer())
          .post('/api/v1/users/roster/import')
          .set('Authorization', `Bearer ${userToken}`)
          .expect(403);

        await request(app.getHttpServer())
          .get('/api/v1/users/roster')
          .set('Authorization', `Bearer ${userToken}`)
          .expect(403);

        await request(app.getHttpServer())
          .delete('/api/v1/users/roster/uuid-123')
          .set('Authorization', `Bearer ${userToken}`)
          .expect(403);
      });

      it('MANAGER role can download template but cannot import or delete', async () => {
        // MANAGER is allowed to download template
        await request(app.getHttpServer())
          .get('/api/v1/users/roster/template')
          .set('Authorization', `Bearer ${managerToken}`)
          .expect(200);

        // MANAGER cannot import roster
        await request(app.getHttpServer())
          .post('/api/v1/users/roster/import')
          .set('Authorization', `Bearer ${managerToken}`)
          .expect(403);

        // MANAGER cannot delete roster
        await request(app.getHttpServer())
          .delete('/api/v1/users/roster/uuid-123')
          .set('Authorization', `Bearer ${managerToken}`)
          .expect(403);
      });

      it('ADMIN role has access to all roster endpoints', async () => {
        await request(app.getHttpServer())
          .get('/api/v1/users/roster/template')
          .set('Authorization', `Bearer ${adminToken}`)
          .expect(200);

        await request(app.getHttpServer())
          .get('/api/v1/users/roster')
          .set('Authorization', `Bearer ${adminToken}`)
          .expect(200);

        await request(app.getHttpServer())
          .delete('/api/v1/users/roster/uuid-123')
          .set('Authorization', `Bearer ${adminToken}`)
          .expect(200);
      });
    });

    describe('Route Precedence & Multipart Streaming', () => {
      it('GET /api/v1/users/roster/template routes to template download, not users/:id', async () => {
        await request(app.getHttpServer())
          .get('/api/v1/users/roster/template')
          .set('Authorization', `Bearer ${adminToken}`)
          .expect(200);

        expect(proxyService.forward).toHaveBeenCalledWith(
          ServiceName.USER,
          expect.anything(),
          '/api/v1/users/roster/template',
          false,
          true,
        );
      });

      it('POST /api/v1/users/roster/import handles multipart/form-data upload and forwards to user-service', async () => {
        const dummyExcelBuffer = Buffer.from('test-excel-file-binary');

        await request(app.getHttpServer())
          .post('/api/v1/users/roster/import')
          .set('Authorization', `Bearer ${adminToken}`)
          .attach('file', dummyExcelBuffer, 'roster.xlsx')
          .expect(200);

        expect(proxyService.forward).toHaveBeenCalledWith(
          ServiceName.USER,
          expect.anything(),
          '/api/v1/users/roster/import',
        );
      });
    });
  });
});
