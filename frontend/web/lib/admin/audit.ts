// Human wording for the audit log (FR-20). Unknown actions fall back to a readable form of the code.

const LABELS: Record<string, string> = {
  CATEGORY_CREATED: 'Category created',
  CATEGORY_RENAMED: 'Category changed',
  CATEGORY_DELETED: 'Category deleted',
  CATEGORY_ARCHIVED: 'Category archived',
  CATEGORY_RESTORED: 'Category restored',
  DEPARTMENT_CREATED: 'Department created',
  DEPARTMENT_RENAMED: 'Department changed',
  DEPARTMENT_DELETED: 'Department deleted',
  DEPARTMENT_ARCHIVED: 'Department archived',
  DEPARTMENT_RESTORED: 'Department restored',
  DOCUMENT_UPLOADED: 'Document uploaded',
  DOCUMENT_VERSION_UPLOADED: 'New document version uploaded',
  DOCUMENT_RETRY_REQUESTED: 'Document reprocessing requested',
  DOCUMENT_METADATA_UPDATED: 'Document metadata edited',
  DOCUMENT_VISIBILITY_UPDATED: 'Document access changed',
  DOCUMENT_OWNERSHIP_CHANGED: 'Document ownership transferred',
  DOCUMENT_DELETED: 'Document deleted',
  INVITATION_CREATED: 'Invitation created',
  INVITATION_REVOKED: 'Invitation revoked',
  INVITATION_ACCEPTED: 'Invitation accepted',
  MEMBER_PROFILE_UPDATED: 'Member profile edited',
  MEMBER_DEPARTMENT_CHANGED: 'Member department changed',
  MEMBER_ROLE_CHANGED: 'Member role changed',
  MEMBER_SUSPENDED: 'Member suspended',
  MEMBER_REACTIVATED: 'Member reactivated',
  MEMBER_REMOVED: 'Member removed',
  PUBLISHER_ASSIGNED: 'Publisher assigned',
  PUBLISHER_UNASSIGNED: 'Publisher removed',
  WORKSPACE_CREATED: 'Workspace created',
  WORKSPACE_RENAMED: 'Workspace renamed',
  WORKSPACE_DELETED: 'Workspace deleted',
};

export const AUDIT_ACTIONS: readonly { value: string; label: string }[] = Object.entries(LABELS).map(
  ([value, label]) => ({ value, label }),
);

export function auditActionLabel(action: string): string {
  const known = LABELS[action];
  if (known) return known;
  const words = action.toLowerCase().replace(/_/g, ' ').trim();
  return words === '' ? 'Unknown action' : words.charAt(0).toUpperCase() + words.slice(1);
}

const MAX_VALUE = 60;

function scalar(value: unknown): string | null {
  if (typeof value === 'string') return value.length > MAX_VALUE ? `${value.slice(0, MAX_VALUE)}…` : value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.length === 0 ? '(none)' : `${value.length} item${value.length === 1 ? '' : 's'}`;
  return null;
}

/** A short `key: value` summary; nested objects are skipped rather than dumped. */
export function summarizeDetails(details: Record<string, unknown> | null | undefined): string {
  if (!details) return '';
  const parts: string[] = [];
  for (const [key, value] of Object.entries(details)) {
    if (value === null || value === undefined) continue;
    const text = scalar(value);
    if (text !== null) parts.push(`${key}: ${text}`);
  }
  return parts.join(' · ');
}

/** `datetime-local` text (no zone) to the ISO instant the API expects, or undefined when empty/invalid. */
export function localToIso(value: string): string | undefined {
  if (value.trim() === '') return undefined;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}
