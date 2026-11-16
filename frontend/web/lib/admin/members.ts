// Which member actions the UI offers. Mirrors TECH-V2-core-api §3.2 for display only: the server
// decides and its fixed error text is shown when it refuses.

import type { WorkspaceRole } from '@/lib/api/types';

export const ROLE_LABEL: Record<WorkspaceRole, string> = { OWNER: 'Owner', ADMIN: 'Admin', MEMBER: 'Member' };

/** Roles the actor may assign to the target; an admin neither touches an owner nor makes one. */
export function assignableRoles(actor: WorkspaceRole, target: WorkspaceRole): WorkspaceRole[] {
  if (actor === 'OWNER') return ['OWNER', 'ADMIN', 'MEMBER'];
  if (actor === 'ADMIN' && target !== 'OWNER') return ['ADMIN', 'MEMBER'];
  return [];
}

export function canActOnMember(actor: WorkspaceRole, target: WorkspaceRole, isSelf: boolean): boolean {
  if (isSelf) return false;
  if (actor === 'OWNER') return true;
  return actor === 'ADMIN' && target !== 'OWNER';
}

/** Roles an invitation can carry: an invitation never creates an owner. */
export const INVITABLE_ROLES: readonly WorkspaceRole[] = ['ADMIN', 'MEMBER'];

/** Departments only make sense once more than one person shares the workspace. */
export function showDepartments(kind: string | undefined, memberCount: number | null): boolean {
  if (kind === 'PERSONAL') return false;
  return memberCount === null || memberCount > 1;
}

/** `null` when blank so the API clears the field. */
export function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}
