import { updateMember } from '@/lib/api/endpoints';

export interface MoveResult {
  moved: string[];
  /** Person ids the server refused, so the caller can say who is still where they were. */
  failed: { userId: string; error: unknown }[];
}

/**
 * Puts each person in `departmentId` (null = no department), one request each, in parallel. There is
 * no batch endpoint, and each person succeeds or fails on its own, like multi-file upload.
 */
export async function moveMembers(userIds: readonly string[], departmentId: string | null): Promise<MoveResult> {
  const settled = await Promise.allSettled(userIds.map((id) => updateMember(id, { departmentId })));
  const result: MoveResult = { moved: [], failed: [] };
  settled.forEach((s, i) => {
    if (s.status === 'fulfilled') result.moved.push(userIds[i]);
    else result.failed.push({ userId: userIds[i], error: s.reason });
  });
  return result;
}
