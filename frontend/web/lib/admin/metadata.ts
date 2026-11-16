// Pure rules of the document metadata form (V2-25 §2a, owner decision 2026-11-12). The server
// stays the authority; these rules only decide what the form sends and when it can be submitted.

import type { DocumentPatch } from '@/lib/api/endpoints';
import type { DocumentView, FieldSource } from '@/lib/api/types';

export interface MetadataForm {
  title: string;
  description: string;
  language: string;
  categoryId: string;
  /** Comma separated, as typed. */
  tags: string;
}

export function formFromDocument(doc: DocumentView): MetadataForm {
  return {
    title: doc.title,
    description: doc.description ?? '',
    language: doc.language ?? '',
    categoryId: doc.category?.id ?? '',
    tags: doc.tags.join(', '),
  };
}

/** Trimmed, de-duplicated (case-insensitively, first spelling wins), empty entries dropped. */
export function parseTags(text: string): string[] {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const raw of text.split(/[,\n]/)) {
    const tag = raw.trim();
    const key = tag.toLowerCase();
    if (tag === '' || seen.has(key)) continue;
    seen.add(key);
    tags.push(tag);
  }
  return tags;
}

/** The server returns tags sorted, so order alone is not a change. */
function sameTags(a: readonly string[], b: readonly string[]): boolean {
  const key = (tags: readonly string[]) => [...tags].map((t) => t.toLowerCase()).sort().join('\u0000');
  return a.length === b.length && key(a) === key(b);
}

/**
 * Only the fields that changed. An empty title means "keep the current one": the backend refuses
 * an empty title, so the key is dropped instead of sent. A cleared description, language or
 * category is sent as `null`.
 */
export function buildDocumentPatch(doc: DocumentView, form: MetadataForm): DocumentPatch {
  const patch: DocumentPatch = {};
  const title = form.title.trim();
  if (title !== '' && title !== doc.title) patch.title = title;
  const description = form.description.trim();
  if (description !== (doc.description ?? '')) patch.description = description === '' ? null : description;
  const language = form.language.trim();
  if (language !== (doc.language ?? '')) patch.language = language === '' ? null : language;
  if (form.categoryId !== (doc.category?.id ?? '')) patch.categoryId = form.categoryId === '' ? null : form.categoryId;
  const tags = parseTags(form.tags);
  if (!sameTags(tags, doc.tags)) patch.tags = tags;
  return patch;
}

export type MetadataErrors = Partial<Record<'description' | 'categoryId' | 'tags', string>>;

/**
 * UI-only completeness rules: a description and at least one tag; a category only when the
 * workspace already has categories to choose from (V2-25 §2a).
 */
export function validateMetadata(form: MetadataForm, hasCategories: boolean): MetadataErrors {
  const errors: MetadataErrors = {};
  if (form.description.trim() === '') errors.description = 'Add a short description.';
  if (hasCategories && form.categoryId === '') errors.categoryId = 'Choose a category.';
  if (parseTags(form.tags).length === 0) errors.tags = 'Add at least one tag.';
  return errors;
}

export function sourceLabel(source: FieldSource | null | undefined): string | null {
  if (source === 'USER') return 'Set by you';
  if (source === 'SUGGESTED') return 'Suggested automatically';
  if (source === 'SYSTEM') return 'Default';
  return null;
}

export type VisibilityChoice = 'WORKSPACE' | 'DEPARTMENTS';

export type AccessPlan =
  | { action: 'none' }
  /** `PUT /visibility`: the reader list of a department document, same scope and owner department. */
  | { action: 'visibility'; visibility: 'DEPARTMENTS'; departmentIds: string[] }
  /** `PUT /ownership` (OWNER only, ADR-009 decision 8): another scope or another owner department. */
  | { action: 'transfer'; visibility: VisibilityChoice; ownerDepartmentId: string | null; departmentIds: string[] }
  | { action: 'blocked'; reason: string };

export const NEEDS_PUBLISHER = 'Only the publisher responsible for this document can change who reads it.';

/**
 * Whether the caller is the responsible publisher of the document (`DocumentWritePolicy`): the
 * workspace publisher for a workspace document, the owning department's publisher for a department
 * document. OWNER and ADMIN roles grant no write access by themselves (ADR-009).
 */
export function canWriteDocument(
  publisherOf: { workspace: boolean; departmentId: string | null } | undefined,
  doc: Pick<DocumentView, 'visibility' | 'ownerDepartment'>,
): boolean {
  if (!publisherOf) return false;
  if (doc.visibility === 'DEPARTMENTS') {
    return publisherOf.departmentId != null && publisherOf.departmentId === doc.ownerDepartment?.id;
  }
  return publisherOf.workspace;
}

/** Edit is offered to the responsible publisher and to an OWNER (who may transfer); never to an ADMIN alone. */
export function canEditDetails(
  publisherOf: { workspace: boolean; departmentId: string | null } | undefined,
  role: string | undefined,
  doc: Pick<DocumentView, 'visibility' | 'ownerDepartment' | 'fieldSources'>,
): boolean {
  return doc.fieldSources != null && (role === 'OWNER' || canWriteDocument(publisherOf, doc));
}

export const NEEDS_OWNER =
  'Moving this document between the whole workspace and departments, or to another owning department, needs a workspace owner.';

/**
 * What saving the access section would do. A publisher may only change who reads inside the same
 * scope; switching the scope or the owning department changes who may write, which only an OWNER
 * does (ADR-009 decision 8, `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`). The owner department always
 * stays in the reader list of a department document.
 */
export function planAccess(
  doc: Pick<DocumentView, 'visibility' | 'departments' | 'ownerDepartment'>,
  target: { visibility: VisibilityChoice; departmentIds: readonly string[]; ownerDepartmentId: string | null },
  who: { isOwner: boolean; canWrite: boolean },
): AccessPlan {
  const { isOwner, canWrite } = who;
  const currentOwner = doc.ownerDepartment?.id ?? null;
  const transfer = (plan: AccessPlan): AccessPlan => (isOwner ? plan : { action: 'blocked', reason: NEEDS_OWNER });

  if (target.visibility === 'WORKSPACE') {
    if (doc.visibility !== 'DEPARTMENTS') return { action: 'none' };
    return transfer({ action: 'transfer', visibility: 'WORKSPACE', ownerDepartmentId: null, departmentIds: [] });
  }

  const owner = target.ownerDepartmentId ?? currentOwner ?? target.departmentIds[0] ?? null;
  if (owner === null) return { action: 'blocked', reason: 'Choose at least one department.' };
  const ids = [...new Set([owner, ...target.departmentIds])];

  if (doc.visibility !== 'DEPARTMENTS' || owner !== currentOwner) {
    return transfer({ action: 'transfer', visibility: 'DEPARTMENTS', ownerDepartmentId: owner, departmentIds: ids });
  }
  const current = new Set((doc.departments ?? []).map((d) => d.id));
  const same = current.size === ids.length && ids.every((id) => current.has(id));
  if (same) return { action: 'none' };
  if (canWrite) return { action: 'visibility', visibility: 'DEPARTMENTS', departmentIds: ids };
  // `PUT /visibility` is publisher-only; an OWNER who is not the publisher goes through the transfer
  // endpoint with the owner department unchanged.
  if (isOwner) return { action: 'transfer', visibility: 'DEPARTMENTS', ownerDepartmentId: owner, departmentIds: ids };
  return { action: 'blocked', reason: NEEDS_PUBLISHER };
}

/** The suggestion is still open when it proposes something the document does not have yet. */
export function hasOpenSuggestion(doc: Pick<DocumentView, 'title' | 'suggestions'>): boolean {
  const s = doc.suggestions;
  if (!s) return false;
  return (s.title != null && s.title !== doc.title) || s.proposedCategoryName != null;
}
