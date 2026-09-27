import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import {
  IJwtPayload,
  IUserContext,
  UserRole,
  AccountStatus,
} from '../../common/interfaces';
import { Logger } from '@nestjs/common';

export interface SignOptions {
  identityKind?: string;
  workspaceId?: string;
  expiresIn?: string | number;
}

@Injectable()
export class JwtAuthService {
  private readonly secret: string;
  private readonly issuer: string;
  private readonly logger = new Logger(JwtAuthService.name);

  constructor(private readonly configService: ConfigService) {
    this.secret = this.configService.getOrThrow<string>('jwt.secret');
    this.issuer =
      this.configService.get<string>('jwt.issuer') || 'poliwise-auth';
  }

  sign(payload: Partial<IJwtPayload>, options?: SignOptions): string {
    const defaultExpiresIn = '8h';
    const signOptions: jwt.SignOptions = {
      expiresIn: (options?.expiresIn || defaultExpiresIn) as any,
      issuer: this.issuer,
    };

    const jwtPayload: jwt.JwtPayload = {
      sub: payload.sub || '',
      username: payload.username || '',
      email: payload.email || '',
      role: payload.role || UserRole.USER,
      status: payload.status || AccountStatus.ACTIVE,
      department: payload.department || null,
      jti: payload.jti || this.generateJti(),
      mustChangePassword: payload.mustChangePassword,
    };

    if (options?.identityKind) {
      jwtPayload.identityKind = options.identityKind;
    }
    if (options?.workspaceId) {
      jwtPayload.workspaceId = options.workspaceId;
    }

    return jwt.sign(jwtPayload, this.secret, signOptions);
  }

  private generateJti(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
  }

  verifyToken(token: string): IJwtPayload | null {
    try {
      const decoded = jwt.verify(token, this.secret, {
        issuer: this.issuer,
      }) as jwt.JwtPayload;

      return {
        sub: decoded.sub as string,
        username: decoded.username as string,
        email: decoded.email as string,
        role: decoded.role as UserRole,
        status: decoded.status as AccountStatus,
        department: decoded.department as string | null,
        iat: decoded.iat as number,
        exp: decoded.exp as number,
        iss: decoded.iss as string,
        jti: decoded.jti as string,
        mustChangePassword: decoded.mustChangePassword as boolean | undefined,
      };
    } catch (error) {
      if (error instanceof jwt.TokenExpiredError) {
        this.logger.warn(`Token expired: ${error.message}`);
      } else if (error instanceof jwt.JsonWebTokenError) {
        this.logger.warn(`Invalid token: ${error.message}`);
      } else {
        this.logger.error(`Token verification error: ${error}`);
      }
      return null;
    }
  }

  decodeToken(token: string): IJwtPayload | null {
    try {
      const decoded = jwt.decode(token) as jwt.JwtPayload;

      if (!decoded) {
        return null;
      }

      return {
        sub: decoded.sub as string,
        username: decoded.username as string,
        email: decoded.email as string,
        role: decoded.role as UserRole,
        status: decoded.status as AccountStatus,
        department: decoded.department as string | null,
        iat: decoded.iat as number,
        exp: decoded.exp as number,
        iss: decoded.iss as string,
        jti: decoded.jti as string,
        mustChangePassword: decoded.mustChangePassword as boolean | undefined,
      };
    } catch (error) {
      this.logger.error(`Token decode error: ${error}`);
      return null;
    }
  }

  isTokenExpired(payload: IJwtPayload): boolean {
    const now = Math.floor(Date.now() / 1000);
    return payload.exp < now;
  }

  extractTokenFromHeader(authHeader: string | undefined): string | null {
    if (!authHeader) {
      return null;
    }

    const parts = authHeader.split(' ');
    if (parts.length !== 2 || parts[0].toLowerCase() !== 'bearer') {
      return null;
    }

    return parts[1];
  }

  buildUserContext(payload: IJwtPayload): IUserContext {
    return {
      userId: payload.sub,
      username: payload.username,
      email: payload.email,
      role: payload.role,
      status: payload.status,
      department: payload.department,
      jti: payload.jti,
      mustChangePassword: payload.mustChangePassword,
    };
  }
}
