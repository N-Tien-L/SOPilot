import {
  Controller,
  Get,
  Query,
  Req,
  Res,
  Logger,
  InternalServerErrorException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Response, Request } from 'express';
import axios from 'axios';
import * as crypto from 'crypto';
import { JwtAuthService } from './services/jwt-auth.service';
import { Public } from '../common/decorators';
import { UserRole, AccountStatus } from '../common/interfaces';

const GOOGLE_JWKS_URL = 'https://www.googleapis.com/oauth2/v3/certs';
const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token';

interface GoogleJwksKey {
  kid: string;
  kty: string;
  alg: string;
  use: string;
  n: string;
  e: string;
}

interface GoogleIdTokenPayload {
  sub: string;
  email: string;
  name: string;
  picture: string;
  iss: string;
  aud: string;
  exp: number;
}

interface GoogleTokenResponse {
  access_token: string;
  expires_in: number;
  token_type: string;
  id_token: string;
  refresh_token?: string;
  scope?: string;
}

interface UpsertGoogleUserRequest {
  googleId: string;
  email: string;
  name: string;
  picture?: string;
}

interface UpsertGoogleUserResponse {
  userId: string;
  username: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  department?: string | null;
  mustChangePassword?: boolean;
}

@Controller('auth/google')
export class GoogleOAuthController {
  private readonly logger = new Logger(GoogleOAuthController.name);
  private _jwksCache: Map<string, GoogleJwksKey> = new Map();
  private _jwksExpiry: number = 0;

  constructor(
    private readonly configService: ConfigService,
    private readonly jwtAuthService: JwtAuthService,
  ) {}

  @Public()
  @Get('login')
  login(@Res() res: Response): void {
    const clientId = this.configService.getOrThrow<string>(
      'oauth.google.clientId',
    );
    const redirectUri = this.configService.getOrThrow<string>(
      'oauth.google.redirectUri',
    );

    const state = this.generateState();

    res.cookie('oauth_state', state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 10 * 60 * 1000,
    });

    const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
    authUrl.searchParams.set('client_id', clientId);
    authUrl.searchParams.set('redirect_uri', redirectUri);
    authUrl.searchParams.set('scope', 'openid email profile');
    authUrl.searchParams.set('state', state);
    authUrl.searchParams.set('response_type', 'code');

    this.logger.debug(`Redirecting to Google OAuth: ${authUrl.toString()}`);
    res.redirect(authUrl.toString());
  }

  @Public()
  @Get('callback')
  async callback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Query('error') error: string,
    @Req() req: Request,
    @Res() res: Response,
  ): Promise<void> {
    if (error) {
      this.logger.warn(`Google OAuth error: ${error}`);
      throw new UnauthorizedException(`Google OAuth error: ${error}`);
    }

    if (!code) {
      throw new UnauthorizedException('Missing authorization code');
    }

    const storedState = (req.cookies as Record<string, string>)?.oauth_state;
    if (!storedState || storedState !== state) {
      this.logger.warn('State mismatch in Google OAuth callback');
      throw new UnauthorizedException('Invalid state parameter');
    }

    try {
      const tokenResponse = await this.exchangeCode(code);
      const idTokenPayload = await this.verifyIdToken(tokenResponse.id_token);

      const authServiceUrl =
        this.configService.getOrThrow<string>('services.auth');
      const internalServiceToken = this.configService.getOrThrow<string>(
        'internal.serviceToken',
      );

      const upsertRequest: UpsertGoogleUserRequest = {
        googleId: idTokenPayload.sub,
        email: idTokenPayload.email,
        name: idTokenPayload.name,
        picture: idTokenPayload.picture,
      };

      const upsertResponse = await axios.post<UpsertGoogleUserResponse>(
        `${authServiceUrl}/api/v1/auth/oauth/google/upsert`,
        upsertRequest,
        {
          headers: {
            'X-Internal-Service-Token': internalServiceToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000,
        },
      );

      const userData = upsertResponse.data;

      const poliwiseToken = this.jwtAuthService.sign(
        {
          sub: userData.userId,
          username: userData.username,
          email: userData.email,
          role: userData.role,
          status: userData.status,
          department: userData.department || null,
          mustChangePassword: userData.mustChangePassword,
        },
        { identityKind: 'demo' },
      );

      const frontendLoginPage =
        this.configService.get<string>('frontend.loginUrl') ||
        'http://localhost:3000/auth/login';
      const redirectUrl = new URL(frontendLoginPage);
      redirectUrl.searchParams.set('token', poliwiseToken);
      redirectUrl.searchParams.set('status', userData.status);

      res.clearCookie('oauth_state');
      this.logger.log(`Google OAuth successful for user: ${userData.email}`);
      res.redirect(redirectUrl.toString());
    } catch (error) {
      this.logger.error(`Google OAuth callback error: ${error}`);
      if (error instanceof UnauthorizedException) {
        throw error;
      }
      throw new InternalServerErrorException(
        'Failed to process Google OAuth callback',
      );
    }
  }

  private async fetchJwks(): Promise<Map<string, GoogleJwksKey>> {
    const now = Date.now();
    if (this._jwksCache.size > 0 && now < this._jwksExpiry) {
      return this._jwksCache;
    }

    try {
      const response = await axios.get<{ keys: GoogleJwksKey[] }>(
        GOOGLE_JWKS_URL,
        {
          timeout: 5000,
        },
      );

      this._jwksCache.clear();
      for (const key of response.data.keys) {
        this._jwksCache.set(key.kid, key);
      }
      this._jwksExpiry = now + 60 * 60 * 1000;

      return this._jwksCache;
    } catch (error) {
      this.logger.error(`Failed to fetch JWKS: ${error}`);
      throw new InternalServerErrorException('Failed to fetch Google JWKS');
    }
  }

  private async verifyIdToken(idToken: string): Promise<GoogleIdTokenPayload> {
    const parts = idToken.split('.');
    if (parts.length !== 3) {
      throw new UnauthorizedException('Invalid ID token format');
    }

    const header = JSON.parse(
      Buffer.from(parts[0], 'base64url').toString('utf-8'),
    );
    const kid = header.kid;
    const alg = header.alg;

    if (alg !== 'RS256') {
      throw new UnauthorizedException(`Unsupported ID token algorithm: ${alg}`);
    }

    const jwks = await this.fetchJwks();
    const key = jwks.get(kid);

    if (!key) {
      throw new UnauthorizedException('Unable to find matching JWKS key');
    }

    const publicKey = this.jwksToPem(key);

    const verify = crypto.createVerify('RSA-SHA256');
    verify.update(`${parts[0]}.${parts[1]}`);

    const isValid = verify.verify(publicKey, parts[2], 'base64');

    if (!isValid) {
      throw new UnauthorizedException('Invalid ID token signature');
    }

    const decodedPayload = JSON.parse(
      Buffer.from(parts[1], 'base64url').toString('utf-8'),
    );

    const clientId = this.configService.getOrThrow<string>(
      'oauth.google.clientId',
    );
    if (decodedPayload.aud !== clientId) {
      throw new UnauthorizedException('Invalid ID token audience');
    }

    if (decodedPayload.iss !== 'https://accounts.google.com') {
      throw new UnauthorizedException('Invalid ID token issuer');
    }

    const now = Math.floor(Date.now() / 1000);
    if (decodedPayload.exp && decodedPayload.exp < now) {
      throw new UnauthorizedException('ID token has expired');
    }

    return decodedPayload as GoogleIdTokenPayload;
  }

  private jwksToPem(key: GoogleJwksKey): string {
    const modulus = Buffer.from(key.n, 'base64url');
    const exponent = Buffer.from(key.e, 'base64url');

    const modulusLength = modulus.length;
    const offsetModulus = modulus[0] & 0x80 ? 0 : 1;
    const modLen = modulusLength + offsetModulus;

    const expLen = exponent.length;
    const offsetExp = exponent[0] & 0x80 ? 0 : 1;
    const expLenField = expLen + offsetExp;

    const totalLen = 4 + modLen + 4 + expLenField;
    const buf = Buffer.alloc(totalLen);

    let pos = 0;
    buf[pos++] = 0x30;
    buf[pos++] = totalLen - 2;

    buf[pos++] = 0x02;
    buf[pos++] = modLen;
    if (offsetModulus) {
      buf[pos++] = 0x00;
    }
    modulus.copy(buf, pos);
    pos += modulusLength;

    buf[pos++] = 0x02;
    buf[pos++] = expLenField;
    if (offsetExp) {
      buf[pos++] = 0x00;
    }
    exponent.copy(buf, pos);

    const der = buf.toString('base64');
    const pem = `-----BEGIN RSA PUBLIC KEY-----\n${der.match(/.{1,64}/g)?.join('\n')}\n-----END RSA PUBLIC KEY-----`;

    return pem;
  }

  private async exchangeCode(code: string): Promise<GoogleTokenResponse> {
    const clientId = this.configService.getOrThrow<string>(
      'oauth.google.clientId',
    );
    const clientSecret = this.configService.getOrThrow<string>(
      'oauth.google.clientSecret',
    );
    const redirectUri = this.configService.getOrThrow<string>(
      'oauth.google.redirectUri',
    );

    try {
      const response = await axios.post<GoogleTokenResponse>(
        GOOGLE_TOKEN_URL,
        new URLSearchParams({
          code,
          client_id: clientId,
          client_secret: clientSecret,
          redirect_uri: redirectUri,
          grant_type: 'authorization_code',
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          timeout: 10000,
        },
      );

      return response.data;
    } catch (error) {
      this.logger.error(`Failed to exchange code for tokens: ${error}`);
      throw new InternalServerErrorException(
        'Failed to exchange authorization code',
      );
    }
  }

  private generateState(): string {
    return crypto.randomBytes(32).toString('hex');
  }
}
