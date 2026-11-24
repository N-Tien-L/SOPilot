// Which member actions the UI offers. Mirrors TECH-V2-core-api §3.2 for display only: the server
// decides and its fixed error text is shown when it refuses.

import type { MemberView, WorkspaceRole } from '@/lib/api/types';

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

/**
 * Departments exist in team workspaces only. They must be reachable while the owner is still alone,
 * because the usual order is: create departments, then invite people straight into them.
 */
export function showDepartments(kind: string | undefined): boolean {
  return kind !== 'PERSONAL';
}

/** The caller may change this person's profile (department included): themselves, or per `canActOnMember`. */
export function canEditProfile(actor: WorkspaceRole, target: WorkspaceRole, isSelf: boolean): boolean {
  return isSelf || canActOnMember(actor, target, false);
}

export const NO_DEPARTMENT = '__none__';

export interface MemberFilters {
  q: string;
  role: string;
  status: string;
  /** A department id, `NO_DEPARTMENT`, or '' for any. */
  departmentId: string;
}

/** Search matches name, email and employee code, case-insensitively; the filters are ANDed. */
export function filterMembers(members: readonly MemberView[], f: MemberFilters): MemberView[] {
  const q = f.q.trim().toLowerCase();
  return members.filter((m) => {
    if (f.role && m.role !== f.role) return false;
    if (f.status && m.status !== f.status) return false;
    if (f.departmentId === NO_DEPARTMENT && m.departmentId !== null) return false;
    if (f.departmentId && f.departmentId !== NO_DEPARTMENT && m.departmentId !== f.departmentId) return false;
    if (!q) return true;
    return [m.displayName, m.email, m.employeeCode ?? ''].some((v) => v.toLowerCase().includes(q));
  });
}

/** `null` when blank so the API clears the field. */
export function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}
