import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy, ExtractJwt } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { JwtAuthService } from '../services/jwt-auth.service';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(
    private readonly configService: ConfigService,
    private readonly jwtAuthService: JwtAuthService,
  ) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: configService.getOrThrow<string>('jwt.secret'),
      issuer: configService.get<string>('jwt.issuer') || 'poliwise-auth',
    });
  }

  async validate(payload: any) {
    return this.jwtAuthService.buildUserContext({
      sub: payload.sub,
      username: payload.username,
      email: payload.email,
      role: payload.role,
      status: payload.status,
      department: payload.department,
      iat: payload.iat,
      exp: payload.exp,
      iss: payload.iss,
      jti: payload.jti,
    });
  }
}
