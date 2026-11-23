import { describe, expect, it } from 'vitest';
import type { DocumentView } from '@/lib/api/types';
import {
  buildDocumentPatch,
  formFromDocument,
  hasOpenSuggestion,
  canWriteDocument,
  sourceLabel,
  planAccess,
  validateMetadata,
} from './metadata';

function doc(overrides: Partial<DocumentView> = {}): DocumentView {
  return {
    id: 'd1',
    title: 'Leave policy',
    description: 'How leave works',
    preparedBy: 'HR department',
    category: { id: 'c1', name: 'HR' },
    tags: ['hr', 'leave'],
    language: 'en',
    visibility: 'WORKSPACE',
    departments: [],
    status: 'READY',
    answerable: true,
    latestVersion: { id: 'v1', versionNo: 1, status: 'READY', failureCode: null, failureMessage: null },
    currentVersion: null,
    createdBy: { id: 'u1', displayName: 'Ann' },
    createdAt: '2026-11-01T00:00:00Z',
    updatedAt: '2026-11-01T00:00:00Z',
    ...overrides,
  };
}

describe('buildDocumentPatch', () => {
  it('is empty when nothing changed', () => {
    const d = doc();
    expect(buildDocumentPatch(d, formFromDocument(d))).toEqual({});
  });

  it('drops an empty title instead of sending it (the backend refuses it)', () => {
    const d = doc();
    expect(buildDocumentPatch(d, { ...formFromDocument(d), title: '   ' })).toEqual({});
  });

  it('sends only the changed fields', () => {
    const d = doc();
    const patch = buildDocumentPatch(d, {
      ...formFromDocument(d),
      title: ' Leave rules ',
      preparedBy: ' People team ',
    });
    expect(patch).toEqual({ title: 'Leave rules', preparedBy: 'People team' });
  });

  it('sends null for a cleared description, language and category', () => {
    const d = doc();
    const patch = buildDocumentPatch(d, { ...formFromDocument(d), description: '', language: '', categoryId: '' });
    expect(patch).toEqual({ description: null, language: null, categoryId: null });
  });

  it('does not clear a field that was already empty', () => {
    const d = doc({ description: null, language: null, category: null });
    expect(buildDocumentPatch(d, formFromDocument(d))).toEqual({});
  });

  it('clears who prepared the document with null, and leaves an already empty value alone', () => {
    const d = doc();
    expect(buildDocumentPatch(d, { ...formFromDocument(d), preparedBy: '  ' })).toEqual({ preparedBy: null });
    const empty = doc({ preparedBy: null });
    expect(buildDocumentPatch(empty, formFromDocument(empty))).toEqual({});
  });
});

describe('validateMetadata', () => {
  const full = { title: 't', description: 'd', language: '', categoryId: 'c1', preparedBy: '' };
  it('accepts a complete form', () => {
    expect(validateMetadata(full, true)).toEqual({});
  });
  it('requires a category only when the workspace has categories', () => {
    expect(validateMetadata({ ...full, categoryId: '' }, false)).toEqual({});
    expect(validateMetadata({ ...full, categoryId: '' }, true)).toHaveProperty('categoryId');
  });
  it('requires a description but never a tag or a preparer', () => {
    expect(Object.keys(validateMetadata({ ...full, description: ' ' }, false))).toEqual(['description']);
    expect(validateMetadata({ ...full, preparedBy: '' }, false)).toEqual({});
  });
});

describe('sourceLabel', () => {
  it('labels the known sources and hides unknown ones', () => {
    expect(sourceLabel('USER')).toBe('Set by you');
    expect(sourceLabel('SUGGESTED')).toBe('Suggested automatically');
    expect(sourceLabel('SYSTEM')).toBe('Default');
    expect(sourceLabel('OTHER')).toBeNull();
    expect(sourceLabel(undefined)).toBeNull();
  });
});

describe('planAccess', () => {
  const PUB = { isOwner: false, canWrite: true };
  const OWN = { isOwner: true, canWrite: false };
  const dept = (id: string) => ({ id, name: id });
  const deptDoc = doc({ visibility: 'DEPARTMENTS', departments: [dept('a'), dept('b')], ownerDepartment: dept('a') });
  const want = (visibility: 'WORKSPACE' | 'DEPARTMENTS', departmentIds: string[], ownerDepartmentId: string | null = null) => ({
    visibility,
    departmentIds,
    ownerDepartmentId,
  });

  it('does nothing when nothing changed', () => {
    expect(planAccess(doc(), want('WORKSPACE', []), PUB)).toEqual({ action: 'none' });
    expect(planAccess(deptDoc, want('DEPARTMENTS', ['b', 'a'], 'a'), PUB)).toEqual({ action: 'none' });
  });

  it('lets a publisher change the reader list inside the same scope, keeping the owner department', () => {
    expect(planAccess(deptDoc, want('DEPARTMENTS', ['b', 'c'], 'a'), PUB)).toEqual({
      action: 'visibility',
      visibility: 'DEPARTMENTS',
      departmentIds: ['a', 'b', 'c'],
    });
  });

  it('blocks a publisher who switches scope or the owner department, and tells them why', () => {
    for (const plan of [
      planAccess(doc(), want('DEPARTMENTS', ['a'], 'a'), PUB),
      planAccess(deptDoc, want('WORKSPACE', []), PUB),
      planAccess(deptDoc, want('DEPARTMENTS', ['a', 'b'], 'b'), PUB),
    ]) {
      expect(plan.action).toBe('blocked');
    }
  });

  it('lets an owner transfer between scopes and owner departments', () => {
    expect(planAccess(doc(), want('DEPARTMENTS', ['b'], 'a'), OWN)).toEqual({
      action: 'transfer',
      visibility: 'DEPARTMENTS',
      ownerDepartmentId: 'a',
      departmentIds: ['a', 'b'],
    });
    expect(planAccess(deptDoc, want('WORKSPACE', []), OWN)).toEqual({
      action: 'transfer',
      visibility: 'WORKSPACE',
      ownerDepartmentId: null,
      departmentIds: [],
    });
    expect(planAccess(deptDoc, want('DEPARTMENTS', ['a', 'b'], 'b'), OWN)).toMatchObject({
      action: 'transfer',
      ownerDepartmentId: 'b',
    });
  });

  it('sends an owner who is not the publisher through the transfer endpoint for a same-scope change', () => {
    expect(planAccess(deptDoc, want('DEPARTMENTS', ['b', 'c'], 'a'), OWN)).toEqual({
      action: 'transfer',
      visibility: 'DEPARTMENTS',
      ownerDepartmentId: 'a',
      departmentIds: ['a', 'b', 'c'],
    });
  });

  it('blocks an admin who is not a publisher', () => {
    expect(planAccess(deptDoc, want('DEPARTMENTS', ['b', 'c'], 'a'), { isOwner: false, canWrite: false }).action).toBe('blocked');
  });

  it('asks for a department when none is chosen', () => {
    expect(planAccess(doc(), want('DEPARTMENTS', []), OWN)).toEqual({ action: 'blocked', reason: 'Choose at least one department.' });
  });

  it('defaults the owner department to the first chosen one', () => {
    expect(planAccess(doc(), want('DEPARTMENTS', ['z', 'y']), OWN)).toMatchObject({ ownerDepartmentId: 'z', departmentIds: ['z', 'y'] });
  });
});

describe('hasOpenSuggestion', () => {
  it('is false without suggestions or when they match the document', () => {
    expect(hasOpenSuggestion(doc())).toBe(false);
    expect(hasOpenSuggestion(doc({ suggestions: { title: 'Leave policy', proposedCategoryName: null } }))).toBe(false);
  });
  it('is true for a different title or a proposed category', () => {
    expect(hasOpenSuggestion(doc({ suggestions: { title: 'Annual leave', proposedCategoryName: null } }))).toBe(true);
    expect(hasOpenSuggestion(doc({ suggestions: { title: null, proposedCategoryName: 'Time off' } }))).toBe(true);
  });
});

describe('canWriteDocument', () => {
  const dept = (id: string) => ({ id, name: id });
  it('uses the workspace publisher for workspace documents', () => {
    expect(canWriteDocument({ workspace: true, departmentId: null }, doc())).toBe(true);
    expect(canWriteDocument({ workspace: false, departmentId: 'a' }, doc())).toBe(false);
  });
  it('uses the owning department publisher for department documents', () => {
    const d = doc({ visibility: 'DEPARTMENTS', ownerDepartment: dept('a') });
    expect(canWriteDocument({ workspace: false, departmentId: 'a' }, d)).toBe(true);
    expect(canWriteDocument({ workspace: false, departmentId: 'b' }, d)).toBe(false);
    expect(canWriteDocument({ workspace: true, departmentId: null }, d)).toBe(false);
    expect(canWriteDocument(undefined, d)).toBe(false);
  });
});
