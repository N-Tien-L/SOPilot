import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import { JwtAuthService, SignOptions } from './jwt-auth.service';
import { UserRole, AccountStatus } from '../../common/interfaces';

describe('JwtAuthService', () => {
  let service: JwtAuthService;
  const testSecret = 'test-secret';
  const testIssuer = 'poliwise-auth-service';

  beforeEach(async () => {
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
      providers: [
        JwtAuthService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
      ],
    }).compile();

    service = module.get<JwtAuthService>(JwtAuthService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('sign', () => {
    it('should sign a payload and return a valid JWT token', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
        department: 'Engineering',
      };

      const token = service.sign(payload);

      expect(token).toBeDefined();
      expect(typeof token).toBe('string');
      expect(token.split('.')).toHaveLength(3);
    });

    it('should include identityKind when provided', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
      };

      const options: SignOptions = { identityKind: 'demo' };
      const token = service.sign(payload, options);

      const decoded = jwt.decode(token) as jwt.JwtPayload;
      expect(decoded.identityKind).toBe('demo');
    });

    it('should include workspaceId when provided', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
      };

      const options: SignOptions = { workspaceId: 'workspace-456' };
      const token = service.sign(payload, options);

      const decoded = jwt.decode(token) as jwt.JwtPayload;
      expect(decoded.workspaceId).toBe('workspace-456');
    });

    it('should sign token with custom expiresIn when provided', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
      };

      const options: SignOptions = { expiresIn: '1h' };
      const token = service.sign(payload, options);

      const decoded = jwt.decode(token) as jwt.JwtPayload & {
        exp: number;
        iat: number;
      };
      const now = Math.floor(Date.now() / 1000);
      const expectedExpiry = now + 3600;

      expect(decoded.exp).toBeGreaterThanOrEqual(expectedExpiry - 5);
      expect(decoded.exp).toBeLessThanOrEqual(expectedExpiry + 5);
    });

    it('should decode signed token and verify sub/username/email/role/status claims', () => {
      const payload = {
        sub: 'user-456',
        username: 'johndoe',
        email: 'john@example.com',
        role: UserRole.MANAGER,
        status: AccountStatus.ACTIVE,
        department: 'Sales',
      };

      const token = service.sign(payload);
      const decoded = jwt.decode(token) as jwt.JwtPayload;

      expect(decoded.sub).toBe('user-456');
      expect(decoded.username).toBe('johndoe');
      expect(decoded.email).toBe('john@example.com');
      expect(decoded.role).toBe(UserRole.MANAGER);
      expect(decoded.status).toBe(AccountStatus.ACTIVE);
      expect(decoded.department).toBe('Sales');
    });

    it('should include jti in signed token', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
      };

      const token = service.sign(payload);
      const decoded = jwt.decode(token) as jwt.JwtPayload;

      expect(decoded.jti).toBeDefined();
      expect(typeof decoded.jti).toBe('string');
    });

    it('should include mustChangePassword when provided', () => {
      const payload = {
        sub: 'user-123',
        username: 'testuser',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
        mustChangePassword: true,
      };

      const token = service.sign(payload);
      const decoded = jwt.decode(token) as jwt.JwtPayload;

      expect(decoded.mustChangePassword).toBe(true);
    });
  });

  describe('verifyToken', () => {
    it('should verify a valid token signed by sign()', () => {
      const payload = {
        sub: 'user-789',
        username: 'verifytest',
        email: 'verify@example.com',
        role: UserRole.ADMIN,
        status: AccountStatus.ACTIVE,
        department: 'IT',
      };

      const token = service.sign(payload);
      const result = service.verifyToken(token);

      expect(result).not.toBeNull();
      expect(result?.sub).toBe('user-789');
      expect(result?.username).toBe('verifytest');
      expect(result?.email).toBe('verify@example.com');
      expect(result?.role).toBe(UserRole.ADMIN);
      expect(result?.status).toBe(AccountStatus.ACTIVE);
      expect(result?.department).toBe('IT');
    });

    it('should return null for invalid token', () => {
      const result = service.verifyToken('invalid.token.here');
      expect(result).toBeNull();
    });

    it('should return null for expired token', () => {
      const expiredToken = jwt.sign(
        {
          sub: 'user-123',
          username: 'test',
          email: 'test@example.com',
          role: UserRole.USER,
          status: AccountStatus.ACTIVE,
          department: null,
          jti: 'test-jti',
        },
        testSecret,
        {
          expiresIn: '-1s',
          issuer: testIssuer,
        },
      );

      const result = service.verifyToken(expiredToken);
      expect(result).toBeNull();
    });

    it('should return null for token signed with wrong secret', () => {
      const wrongToken = jwt.sign(
        {
          sub: 'user-123',
          username: 'test',
          email: 'test@example.com',
          role: UserRole.USER,
          status: AccountStatus.ACTIVE,
          department: null,
          jti: 'test-jti',
        },
        'wrong-secret',
        {
          expiresIn: '1h',
          issuer: testIssuer,
        },
      );

      const result = service.verifyToken(wrongToken);
      expect(result).toBeNull();
    });
  });

  describe('buildUserContext', () => {
    it('should build user context from payload with identity fields', () => {
      const payload = {
        sub: 'user-123',
        username: 'contextuser',
        email: 'context@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
        department: 'Marketing',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        iss: testIssuer,
        jti: 'context-jti',
        mustChangePassword: false,
      };

      const context = service.buildUserContext(payload);

      expect(context.userId).toBe('user-123');
      expect(context.username).toBe('contextuser');
      expect(context.email).toBe('context@example.com');
      expect(context.role).toBe(UserRole.USER);
      expect(context.status).toBe(AccountStatus.ACTIVE);
      expect(context.department).toBe('Marketing');
      expect(context.jti).toBe('context-jti');
      expect(context.mustChangePassword).toBe(false);
    });

    it('should handle null department', () => {
      const payload = {
        sub: 'user-123',
        username: 'nulluser',
        email: 'null@example.com',
        role: UserRole.MANAGER,
        status: AccountStatus.ACTIVE,
        department: null,
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        iss: testIssuer,
        jti: 'null-jti',
      };

      const context = service.buildUserContext(payload);

      expect(context.department).toBeNull();
    });
  });

  describe('isTokenExpired', () => {
    it('should return true for expired payload', () => {
      const payload = {
        sub: 'user-123',
        username: 'test',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
        department: null,
        iat: Math.floor(Date.now() / 1000) - 7200,
        exp: Math.floor(Date.now() / 1000) - 3600,
        iss: testIssuer,
        jti: 'test-jti',
      };

      expect(service.isTokenExpired(payload)).toBe(true);
    });

    it('should return false for valid payload', () => {
      const payload = {
        sub: 'user-123',
        username: 'test',
        email: 'test@example.com',
        role: UserRole.USER,
        status: AccountStatus.ACTIVE,
        department: null,
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        iss: testIssuer,
        jti: 'test-jti',
      };

      expect(service.isTokenExpired(payload)).toBe(false);
    });
  });

  describe('extractTokenFromHeader', () => {
    it('should extract token from valid Bearer header', () => {
      const token = service.extractTokenFromHeader(
        'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
      );
      expect(token).toBe('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9');
    });

    it('should return null for missing header', () => {
      const token = service.extractTokenFromHeader(undefined);
      expect(token).toBeNull();
    });

    it('should return null for invalid format', () => {
      const token = service.extractTokenFromHeader('InvalidHeader');
      expect(token).toBeNull();
    });

    it('should return null for Basic auth header', () => {
      const token = service.extractTokenFromHeader('Basic dXNlcjpwYXNz');
      expect(token).toBeNull();
    });

    it('should handle lowercase bearer', () => {
      const token = service.extractTokenFromHeader('bearer test-token');
      expect(token).toBe('test-token');
    });
  });
});
