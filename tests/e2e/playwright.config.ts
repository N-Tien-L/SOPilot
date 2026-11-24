import { defineConfig } from '@playwright/test';

// Local only: runs against the stack that is already up (docker compose or from source).
// One worker, files in name order: the specs share one workspace that global-setup builds.
export default defineConfig({
  testDir: './specs',
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'report', open: 'never' }],
    ['json', { outputFile: 'results.json' }],
  ],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    viewport: { width: 1280, height: 800 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
