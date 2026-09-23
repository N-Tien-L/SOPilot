import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
  ForbiddenException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JwtAuthService } from '../../auth/services/jwt-auth.service';
import { IS_PUBLIC_KEY } from '../decorators/public.decorator';
import { AccountStatus } from '../interfaces';
import { ErrorResponse } from '../dto';

@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly jwtAuthService: JwtAuthService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) {
      return true;
    }

    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers['authorization'];

    const token = this.jwtAuthService.extractTokenFromHeader(authHeader);
    if (!token) {
      throw new UnauthorizedException(
        ErrorResponse.unauthorized('No valid authorization token provided'),
      );
    }

    const payload = this.jwtAuthService.verifyToken(token);
    if (!payload) {
      throw new UnauthorizedException(
        ErrorResponse.unauthorized('Invalid or expired token'),
      );
    }

    if (payload.status === AccountStatus.DEACTIVATED) {
      throw new ForbiddenException(ErrorResponse.accountDeactivated());
    }

    if (payload.status === AccountStatus.REVOKED) {
      throw new ForbiddenException(ErrorResponse.accountRevoked());
    }

    const userContext = this.jwtAuthService.buildUserContext(payload);
    request.user = userContext;

    if (payload.mustChangePassword === true) {
      const path = (request.url || request.path || '').split('?')[0];
      const isChangePassword =
        path === '/api/v1/auth/change-password' ||
        path.endsWith('/api/v1/auth/change-password') ||
        path === '/api/v1/auth/logout' ||
        path.endsWith('/api/v1/auth/logout');
      if (!isChangePassword) {
        throw new ForbiddenException(
          ErrorResponse.forbidden('Password change required before continuing'),
        );
      }
    }

    return true;
  }
}
