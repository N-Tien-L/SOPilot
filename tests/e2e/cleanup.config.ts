import { defineConfig } from '@playwright/test';

// `pnpm cleanup`: deletes the workspace that a run kept with E2E_KEEP=1. No global setup, so nothing is created.
export default defineConfig({ testDir: './cleanup', reporter: 'list', workers: 1 });
