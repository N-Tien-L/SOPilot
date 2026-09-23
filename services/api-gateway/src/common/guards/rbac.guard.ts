import {
  Injectable,
  CanActivate,
  ExecutionContext,
  ForbiddenException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from '../decorators/roles.decorator';
import { UserRole, IUserContext } from '../interfaces';
import { ErrorResponse } from '../dto';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<UserRole[]>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );

    if (!requiredRoles || requiredRoles.length === 0) {
      return true;
    }

    const request = context.switchToHttp().getRequest();
    const user = request.user as IUserContext;

    if (!user) {
      throw new ForbiddenException(
        ErrorResponse.forbidden('User context not found'),
      );
    }

    const hasRole = requiredRoles.some((role) =>
      this.roleMatches(user.role as UserRole, role),
    );

    if (!hasRole) {
      throw new ForbiddenException(
        ErrorResponse.forbidden(
          `Access denied. Required role: ${requiredRoles.join(' or ')}. Your role: ${user.role}`,
        ),
      );
    }

    return true;
  }

  private roleMatches(userRole: UserRole, requiredRole: UserRole): boolean {
    const roleHierarchy: Record<UserRole, number> = {
      [UserRole.ADMIN]: 3,
      [UserRole.MANAGER]: 2,
      [UserRole.USER]: 1,
    };

    return roleHierarchy[userRole] >= roleHierarchy[requiredRole];
  }
}
