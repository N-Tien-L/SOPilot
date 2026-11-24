import { request, type APIRequestContext } from '@playwright/test';

/** core-api, called directly for setup and for the checks that need no browser. */
export const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8080';
/** ai-service, for the read-only endpoints a test calls with a core-api token (`base: 'ai'`). */
export const AI_URL = process.env.E2E_AI_URL ?? 'http://localhost:8000';

export interface Session {
  token: string;
  userId: string;
}

export interface Reply {
  status: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  body: any;
}

type Multipart = Record<string, string | { name: string; mimeType: string; buffer: Buffer }>;

export class Api {
  private constructor(private readonly ctx: APIRequestContext) {}

  static async create(): Promise<Api> {
    return new Api(await request.newContext());
  }

  async dispose(): Promise<void> {
    await this.ctx.dispose();
  }

  async healthy(): Promise<boolean> {
    try {
      const res = await this.ctx.fetch(`${API_URL}/actuator/health`, { failOnStatusCode: false });
      return res.ok();
    } catch {
      return false;
    }
  }

  /** Any status is returned, never thrown: a test often expects 403 or 404. */
  async call(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    path: string,
    opts: { token?: string; json?: unknown; multipart?: Multipart; query?: Record<string, string>; base?: 'core' | 'ai' } = {},
  ): Promise<Reply> {
    const url = opts.base === 'ai' ? `${AI_URL}/ai/v1${path}` : `${API_URL}/api/v1${path}`;
    const res = await this.ctx.fetch(url, {
      method,
      headers: opts.token ? { Authorization: `Bearer ${opts.token}` } : undefined,
      data: opts.json,
      multipart: opts.multipart,
      params: opts.query,
      failOnStatusCode: false,
    });
    const text = await res.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = text;
    }
    return { status: res.status(), body };
  }

  /** Throws unless the call succeeded; returns the `data` of the envelope. */
  async ok<T = any>(what: string, reply: Reply | Promise<Reply>): Promise<T> { // eslint-disable-line @typescript-eslint/no-explicit-any
    const r = await reply;
    if (r.status < 200 || r.status >= 300) throw new Error(`${what}: HTTP ${r.status} ${JSON.stringify(r.body)}`);
    return (r.body as { data: T } | null)?.data as T;
  }

  /** Dev login (local profile only). The token is for the user's last active workspace. */
  async login(email: string, displayName: string): Promise<Session> {
    const data = await this.ok('dev-login', this.call('POST', '/auth/dev-login', { json: { email, displayName } }));
    return { token: data.accessToken, userId: data.user.id };
  }

  /** A token for `workspaceId`, which the user must belong to. */
  async switchTo(session: Session, workspaceId: string): Promise<Session> {
    const data = await this.ok(
      'switch-workspace',
      this.call('POST', '/auth/switch-workspace', { token: session.token, json: { workspaceId } }),
    );
    return { ...session, token: data.accessToken };
  }
}
