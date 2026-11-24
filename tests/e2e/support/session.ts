import type { Page } from '@playwright/test';
import { type Persona, type World } from './world';

interface LoginBody {
  data: { accessToken: string };
}

/**
 * Signs the browser in as `persona` in the test workspace without the login form: dev login and a
 * workspace switch set the refresh cookie on the page's context, and the app restores the session
 * from it on the next load. Returns after the first page has finished loading.
 */
export async function signInAs(page: Page, persona: Persona, world: World, path = '/documents'): Promise<void> {
  const login = await page.request.post('/api/v1/auth/dev-login', {
    data: { email: persona.email, displayName: persona.name },
  });
  if (!login.ok()) throw new Error(`dev-login for ${persona.email}: HTTP ${login.status()}`);
  const token = ((await login.json()) as LoginBody).data.accessToken;
  const switched = await page.request.post('/api/v1/auth/switch-workspace', {
    headers: { Authorization: `Bearer ${token}` },
    data: { workspaceId: world.workspaceId },
  });
  if (!switched.ok()) throw new Error(`switch-workspace for ${persona.email}: HTTP ${switched.status()}`);
  await page.goto(path);
}
