import { expect, test } from '@playwright/test';
import { Api } from '../support/api';
import { loadWorld } from '../support/world';

// The documents uploaded in setup must be processed to READY: it proves core-api, the outbox, ai-service and
// the worker work together. It fails (rather than skips) when the worker is down, because that is a finding.

test('an uploaded document is processed until it can answer questions', async () => {
  test.setTimeout(6 * 60_000);
  const world = loadWorld();
  const api = await Api.create();
  try {
    const owner = world.personas.owner;
    const session = await api.switchTo(await api.login(owner.email, owner.name), world.workspaceId);
    for (const doc of [world.docs.company, world.docs.alpha]) {
      await expect
        .poll(
          async () => (await api.call('GET', `/documents/${doc.id}`, { token: session.token })).body?.data?.status,
          { timeout: 5 * 60_000, intervals: [3_000], message: `${doc.title} should reach READY (is ai-worker running?)` },
        )
        .toBe('READY');
      const detail = (await api.call('GET', `/documents/${doc.id}`, { token: session.token })).body.data;
      expect(detail.answerable).toBe(true);
      expect(detail.currentVersion.fileType).toBe('MD');
    }
  } finally {
    await api.dispose();
  }
});
