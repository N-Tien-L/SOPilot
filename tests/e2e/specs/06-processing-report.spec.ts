import { expect, test } from '@playwright/test';
import { Api, type Session } from '../support/api';
import { loadWorld, type PersonaKey, type World } from '../support/world';

// V2-46: the processing report follows the same access rule as the recognized content. It runs after
// 05-ingest-ready, so both documents are READY. Checked through the API on the web origin's /ai proxy path.

let api: Api;
let world: World;
const sessions = {} as Record<PersonaKey, Session>;

test.beforeAll(async () => {
  world = loadWorld();
  api = await Api.create();
  for (const key of ['owner', 'alphaMember', 'betaMember', 'loner'] as PersonaKey[]) {
    const p = world.personas[key];
    sessions[key] = await api.switchTo(await api.login(p.email, p.name), world.workspaceId);
  }
});
test.afterAll(async () => {
  await api.dispose();
});

async function versionOf(docId: string): Promise<string> {
  const detail = await api.call('GET', `/documents/${docId}`, { token: sessions.owner.token });
  return detail.body.data.currentVersion.id as string;
}

const report = async (key: PersonaKey, docId: string, versionId: string, query: Record<string, string> = {}) =>
  api.call('GET', `/documents/${docId}/versions/${versionId}/processing-report`, {
    token: sessions[key].token,
    query,
    base: 'ai',
  });

test('a reader opens the report and sees chunks without their text; a clicked chunk carries its text', async () => {
  const { id } = world.docs.alpha;
  const version = await versionOf(id);
  const res = await report('alphaMember', id, version);
  expect(res.status).toBe(200);
  expect(res.body.family).toMatch(/^(LEGAL_ARTICLES|ISO_PROCEDURE|MARKDOWN|PROSE)$/);
  expect(res.body.chunks.length).toBeGreaterThan(0);
  expect(res.body.chunks[0].content).toBeUndefined();
  const one = await report('alphaMember', id, version, { ordinal: '0' });
  expect(one.status).toBe(200);
  expect(typeof one.body.indexText).toBe('string');
});

test('a person outside the department sees nothing: the report is 404, never 403', async () => {
  const { id } = world.docs.alpha;
  const version = await versionOf(id);
  for (const key of ['betaMember', 'loner'] as PersonaKey[]) {
    expect((await report(key, id, version)).status).toBe(404);
    expect((await report(key, id, version, { ordinal: '0' })).status).toBe(404);
  }
});

test('a workspace document is open to every member', async () => {
  const { id } = world.docs.company;
  const version = await versionOf(id);
  expect((await report('betaMember', id, version)).status).toBe(200);
});
