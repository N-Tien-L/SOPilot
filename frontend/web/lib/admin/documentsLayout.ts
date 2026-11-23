// Which Documents tabs a person gets and what they may upload (ADR-009). Display logic only: the server
// decides and answers `403 NOT_PUBLISHER` when it refuses.

import type { UploadScope } from '@/lib/upload/queue';

export interface PublisherOf {
  workspace: boolean;
  departmentId: string | null;
}

export interface DocumentsLayout {
  /**
   * One Manage tab over every document the person can read: the workspace publisher, and an OWNER
   * (who may delete and transfer anything). No separate read-only tab, they already see it all.
   */
  manageAll: boolean;
  /** A department publisher who is not `manageAll`: a read-only tab for everything, and Manage for this department. */
  manageDepartmentId: string | null;
}

export function documentsLayout(publisherOf: PublisherOf | undefined, role: string | undefined): DocumentsLayout {
  const manageAll = publisherOf?.workspace === true || role === 'OWNER';
  return { manageAll, manageDepartmentId: !manageAll ? (publisherOf?.departmentId ?? null) : null };
}

export interface ScopeChoice {
  key: string;
  scope: UploadScope;
}

/**
 * Where this person may publish: the whole workspace if they are the workspace publisher, and their own
 * department if they are its publisher. An OWNER who is not a publisher gets nothing (never writes content).
 */
export function uploadScopes(publisherOf: PublisherOf | undefined): ScopeChoice[] {
  const out: ScopeChoice[] = [];
  if (publisherOf?.workspace) out.push({ key: 'workspace', scope: { kind: 'WORKSPACE' } });
  if (publisherOf?.departmentId) {
    out.push({ key: `department:${publisherOf.departmentId}`, scope: { kind: 'DEPARTMENT', departmentId: publisherOf.departmentId } });
  }
  return out;
}

export type DocumentsTab = 'view' | 'manage' | 'categories';

export function documentsTabs(layout: DocumentsLayout, isManager: boolean): DocumentsTab[] {
  const tabs: DocumentsTab[] = [];
  if (layout.manageDepartmentId) tabs.push('manage', 'view');
  else if (layout.manageAll) tabs.push('manage');
  else tabs.push('view');
  if (isManager) tabs.push('categories');
  return tabs;
}
