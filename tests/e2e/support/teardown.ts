import { Api } from './api';
import { clearWorld, loadWorld } from './world';

/** Deletes the throwaway workspace of the last run (and with it every document that run uploaded). */
export async function destroyWorld(): Promise<void> {
  const api = await Api.create();
  try {
    const world = loadWorld();
    const owner = world.personas.owner;
    const session = await api.switchTo(await api.login(owner.email, owner.name), world.workspaceId);
    const res = await api.call('DELETE', '/workspaces/current', { token: session.token });
    if (res.status >= 300) {
      console.warn(`e2e cleanup: workspace ${world.workspaceId} was not deleted (HTTP ${res.status}). Delete it in Settings.`);
    }
  } catch (error) {
    console.warn(`e2e cleanup skipped: ${(error as Error).message}`);
  } finally {
    clearWorld();
    await api.dispose();
  }
}
