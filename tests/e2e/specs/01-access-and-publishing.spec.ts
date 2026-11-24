import { expect, test } from '@playwright/test';
import { Api, type Session } from '../support/api';
import { sopMarkdown } from '../support/fixtures';
import { loadWorld, type PersonaKey, type World } from '../support/world';

// Business rules checked through the API, with no browser: who may read a document, who may write one, and
// that nothing outside a reader scope leaks (FR-19, FR-25, ADR-007, ADR-009). Each persona is a real login.

let api: Api;
let world: World;
const sessions = {} as Record<PersonaKey, Session>;

test.beforeAll(async () => {
  world = loadWorld();
  api = await Api.create();
  for (const key of Object.keys(world.personas) as PersonaKey[]) {
    const p = world.personas[key];
    sessions[key] = await api.switchTo(await api.login(p.email, p.name), world.workspaceId);
  }
});
test.afterAll(async () => {
  await api.dispose();
});

const titlesFor = async (key: PersonaKey, query: Record<string, string> = {}): Promise<{ status: number; titles: string[] }> => {
  const res = await api.call('GET', '/documents', { token: sessions[key].token, query: { limit: '100', ...query } });
  return { status: res.status, titles: res.status === 200 ? res.body.data.map((d: { title: string }) => d.title) : [] };
};

test.describe('who can read what', () => {
  test('a department document is read by that department, the owner and the admin, and by nobody else', async () => {
    const title = () => world.docs.alpha.title;
    for (const key of ['alphaMember', 'alphaPub', 'owner', 'admin'] as PersonaKey[]) {
      expect((await titlesFor(key)).titles, `${key} should see it`).toContain(title());
    }
    for (const key of ['betaMember', 'loner', 'wsPub'] as PersonaKey[]) {
      expect((await titlesFor(key)).titles, `${key} must not see it`).not.toContain(title());
    }
  });

  test('opening or downloading a document outside the reader scope is 404, not 403 (nothing is revealed)', async () => {
    const id = () => world.docs.alpha.id;
    for (const key of ['betaMember', 'loner', 'wsPub'] as PersonaKey[]) {
      expect((await api.call('GET', `/documents/${id()}`, { token: sessions[key].token })).status, `${key} detail`).toBe(404);
      expect((await api.call('GET', `/documents/${id()}/download-url`, { token: sessions[key].token })).status, `${key} download`).toBe(404);
    }
    expect((await api.call('GET', `/documents/${id()}`, { token: sessions.alphaMember.token })).status).toBe(200);
  });

  test('a workspace document is read by everyone', async () => {
    for (const key of Object.keys(world.personas) as PersonaKey[]) {
      expect((await titlesFor(key)).titles, `${key} should see the company document`).toContain(world.docs.company.title);
    }
  });

  test('the department filter is open to owners, admins and that department only', async () => {
    const alpha = world.departments.alpha;
    expect((await titlesFor('betaMember', { ownerDepartmentId: alpha })).status).toBe(403);
    expect((await titlesFor('loner', { ownerDepartmentId: alpha })).status).toBe(403);
    const mine = await titlesFor('alphaMember', { ownerDepartmentId: alpha });
    expect(mine.status).toBe(200);
    expect(mine.titles).toEqual([world.docs.alpha.title]);
    expect((await titlesFor('admin', { ownerDepartmentId: alpha })).titles).toEqual([world.docs.alpha.title]);
  });

  test('the visibility filter separates workspace documents from department documents', async () => {
    const workspaceOnly = await titlesFor('alphaMember', { visibility: 'WORKSPACE' });
    expect(workspaceOnly.titles).toContain(world.docs.company.title);
    expect(workspaceOnly.titles).not.toContain(world.docs.alpha.title);
    expect((await titlesFor('owner', { visibility: 'NONSENSE' })).status).toBe(400);
  });
});

test.describe('who can publish', () => {
  test('a department publisher cannot publish for the whole workspace, and the workspace publisher cannot for a department', async () => {
    const body = (title: string) => ({ file: { name: `${title}.md`, mimeType: 'text/markdown', buffer: sopMarkdown(title, `${world.run}x`) }, title });
    const wide = await api.call('POST', '/documents', { token: sessions.alphaPub.token, multipart: { ...body('E2E should not exist 1'), visibility: 'WORKSPACE' } });
    expect(wide.status).toBe(403);
    expect(wide.body.error.code).toBe('NOT_PUBLISHER');
    const dept = await api.call('POST', '/documents', {
      token: sessions.wsPub.token,
      multipart: { ...body('E2E should not exist 2'), visibility: 'DEPARTMENTS', ownerDepartmentId: world.departments.alpha, departmentIds: world.departments.alpha },
    });
    expect(dept.status).toBe(403);
    expect(dept.body.error.code).toBe('NOT_PUBLISHER');
  });

  test('only the responsible publisher edits a document; others are refused without learning it exists', async () => {
    const id = world.docs.alpha.id;
    expect((await api.call('PATCH', `/documents/${id}`, { token: sessions.alphaMember.token, json: { description: 'x' } })).status).toBe(403);
    expect((await api.call('PATCH', `/documents/${id}`, { token: sessions.betaMember.token, json: { description: 'x' } })).status).toBe(404);
    expect((await api.call('PATCH', `/documents/${id}`, { token: sessions.owner.token, json: { description: 'x' } })).status).toBe(403);
  });

  test('ownership of a document is moved by the owner only', async () => {
    const res = await api.call('PUT', `/documents/${world.docs.alpha.id}/ownership`, {
      token: sessions.alphaPub.token,
      json: { visibility: 'WORKSPACE', ownerDepartmentId: null, departmentIds: [] },
    });
    expect([403, 409]).toContain(res.status);
  });
});

test.describe('prepared by (who drafted the content, apart from who published it)', () => {
  test('a department document defaults to the owning department; a workspace document keeps what was typed', async () => {
    const alpha = await api.call('GET', `/documents/${world.docs.alpha.id}`, { token: sessions.alphaMember.token });
    expect(alpha.body.data.preparedBy).toBe('Alpha');
    const company = await api.call('GET', `/documents/${world.docs.company.id}`, { token: sessions.loner.token });
    expect(company.body.data.preparedBy).toBe('HR office');
  });

  test('the publisher can change it, clear it and is refused a value over 100 characters', async () => {
    const id = world.docs.alpha.id;
    const patch = (json: unknown) => api.call('PATCH', `/documents/${id}`, { token: sessions.alphaPub.token, json });
    expect((await patch({ preparedBy: '  QA team ' })).body.data.preparedBy).toBe('QA team');
    expect((await patch({ preparedBy: '   ' })).body.data.preparedBy).toBeNull();
    expect((await patch({ preparedBy: 'x'.repeat(101) })).status).toBe(400);
    expect((await patch({ preparedBy: 'Alpha' })).body.data.preparedBy).toBe('Alpha');
  });
});

test.describe('people', () => {
  test('a member name comes from the account, because the invitation carried none', async () => {
    const members = await api.call('GET', '/members', { token: sessions.owner.token });
    const names = Object.fromEntries(members.body.data.map((m: { email: string; displayName: string }) => [m.email, m.displayName]));
    for (const key of Object.keys(world.personas) as PersonaKey[]) {
      expect(names[world.personas[key].email]).toBe(world.personas[key].name);
    }
  });

  test('a plain member cannot list members, departments of others, publishers write, or the audit log', async () => {
    const t = sessions.betaMember.token;
    expect((await api.call('GET', '/members', { token: t })).status).toBe(403);
    expect((await api.call('GET', '/audit-logs', { token: t })).status).toBe(403);
    expect((await api.call('PUT', '/publishers/workspace', { token: t, json: { userId: world.personas.betaMember.userId } })).status).toBe(403);
    expect((await api.call('POST', '/departments', { token: t, json: { name: 'Nope' } })).status).toBe(403);
  });

  test('an admin manages people but cannot assign publishers', async () => {
    const t = sessions.admin.token;
    expect((await api.call('GET', '/members', { token: t })).status).toBe(200);
    expect((await api.call('PUT', '/publishers/workspace', { token: t, json: { userId: world.personas.admin.userId } })).status).toBe(403);
  });
});
