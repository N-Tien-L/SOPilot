import { Global, Module } from '@nestjs/common';
import { PassportModule } from '@nestjs/passport';
import { JwtModule } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { JwtAuthService } from './services/jwt-auth.service';
import { JwtStrategy } from './strategies/jwt.strategy';
import { GoogleOAuthController } from './google-oauth.controller';

@Global()
@Module({
  imports: [
    PassportModule.register({ defaultStrategy: 'jwt' }),
    JwtModule.registerAsync({
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('jwt.secret'),
        signOptions: {
          expiresIn: '15m',
          issuer: configService.get<string>('jwt.issuer'),
        },
      }),
    }),
  ],
  controllers: [GoogleOAuthController],
  providers: [JwtAuthService, JwtStrategy],
  exports: [JwtAuthService, JwtModule, PassportModule],
})
export class AuthModule {}
