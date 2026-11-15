// After leaving or deleting the current workspace the old token no longer matches a membership:
// move to another workspace of the user (the personal one first), or sign out when there is none.

import { listWorkspaces } from '@/lib/api/endpoints';
import { signOut, switchWorkspace } from './auth';

export async function moveToAnotherWorkspace(leavingId: string): Promise<'switched' | 'signed-out'> {
  const others = (await listWorkspaces()).filter((w) => w.id !== leavingId && w.status === 'ACTIVE');
  const target = others.find((w) => w.kind === 'PERSONAL') ?? others[0];
  if (!target) {
    await signOut();
    return 'signed-out';
  }
  await switchWorkspace(target.id);
  return 'switched';
}
