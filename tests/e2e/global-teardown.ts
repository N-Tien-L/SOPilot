import { destroyWorld } from './support/teardown';

/** `E2E_KEEP=1` keeps the workspace so a person or an agent can look around; `pnpm cleanup` removes it later. */
export default async function globalTeardown(): Promise<void> {
  if (process.env.E2E_KEEP === '1') return;
  await destroyWorld();
}
