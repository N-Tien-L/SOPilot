# NestJS Test Patterns

## 1. Service Unit Test
Use Jest and NestJS testing module to mock dependencies.

```typescript
import { Test, TestingModule } from '@nestjs/testing';
import { JwtAuthService } from './jwt-auth.service';
import { JwtService } from '@nestjs/jwt';

describe('JwtAuthService', () => {
  let service: JwtAuthService;
  let jwtService: JwtService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        JwtAuthService,
        {
          provide: JwtService,
          useValue: {
            verifyAsync: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<JwtAuthService>(JwtAuthService);
    jwtService = module.get<JwtService>(JwtService);
  });

  it('should validate token successfully', async () => {
    // Arrange
    const mockPayload = { userId: 1, username: 'test' };
    jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(mockPayload);

    // Act
    const result = await service.validateToken('valid.token.here');

    // Assert
    expect(result).toEqual(mockPayload);
    expect(jwtService.verifyAsync).toHaveBeenCalledWith('valid.token.here');
  });
});
```

## 2. Controller Test (Supertest)
```typescript
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from './../src/app.module';

describe('AppController (e2e)', () => {
  let app: INestApplication;

  beforeEach(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  it('/health (GET)', () => {
    return request(app.getHttpServer())
      .get('/health')
      .expect(200)
      .expect({ status: 'up' });
  });
});
```
