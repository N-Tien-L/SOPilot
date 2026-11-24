import { test } from '@playwright/test';
import { destroyWorld } from '../support/teardown';

test('delete the throwaway workspace of the last run', async () => {
  await destroyWorld();
});
