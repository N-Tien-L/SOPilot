import { beforeEach, describe, expect, it } from 'vitest';
import { auditActionLabel, localToIso, summarizeDetails } from './audit';
import { clearInviteToken, holdInviteToken, peekInviteToken, readInviteToken } from './invite';
import type { MemberView } from '@/lib/api/types';
import { documentsLayout, documentsTabs, uploadScopes } from './documentsLayout';
import { NO_DEPARTMENT, assignableRoles, blankToNull, canActOnMember, canEditProfile, filterMembers, showDepartments } from './members';

describe('auditActionLabel', () => {
  it('uses the table for known actions', () => {
    expect(auditActionLabel('MEMBER_SUSPENDED')).toBe('Member suspended');
  });
  it('makes unknown codes readable instead of hiding them', () => {
    expect(auditActionLabel('SOMETHING_NEW_HAPPENED')).toBe('Something new happened');
    expect(auditActionLabel('')).toBe('Unknown action');
  });
});

describe('summarizeDetails', () => {
  it('prints scalars and counts arrays, skipping nested objects and nulls', () => {
    expect(
      summarizeDetails({ role: 'ADMIN', n: 3, ok: true, ids: ['a', 'b'], none: [], nested: { x: 1 }, gone: null }),
    ).toBe('role: ADMIN · n: 3 · ok: true · ids: 2 items · none: (none)');
  });
  it('shortens long values and tolerates missing details', () => {
    expect(summarizeDetails({ title: 'x'.repeat(80) })).toBe(`title: ${'x'.repeat(60)}…`);
    expect(summarizeDetails(null)).toBe('');
  });
});

describe('localToIso', () => {
  it('converts a datetime-local value and ignores blank or invalid input', () => {
    expect(localToIso('2026-11-16T10:30')).toBe(new Date('2026-11-16T10:30').toISOString());
    expect(localToIso('')).toBeUndefined();
    expect(localToIso('nonsense')).toBeUndefined();
  });
});

describe('invite token', () => {
  beforeEach(clearInviteToken);
  it('reads the token from the fragment', () => {
    expect(readInviteToken('#token=abc_DEF-1')).toBe('abc_DEF-1');
    expect(readInviteToken('token=abc')).toBe('abc');
  });
  it('returns null when absent or empty', () => {
    expect(readInviteToken('')).toBeNull();
    expect(readInviteToken('#other=1')).toBeNull();
    expect(readInviteToken('#token=  ')).toBeNull();
  });
  it('is held in memory until cleared', () => {
    expect(peekInviteToken()).toBeNull();
    holdInviteToken('t');
    expect(peekInviteToken()).toBe('t');
    clearInviteToken();
    expect(peekInviteToken()).toBeNull();
  });
});

describe('member rules', () => {
  it('lets an owner assign every role and an admin only admin or member on non-owners', () => {
    expect(assignableRoles('OWNER', 'MEMBER')).toEqual(['OWNER', 'ADMIN', 'MEMBER']);
    expect(assignableRoles('ADMIN', 'MEMBER')).toEqual(['ADMIN', 'MEMBER']);
    expect(assignableRoles('ADMIN', 'OWNER')).toEqual([]);
    expect(assignableRoles('MEMBER', 'MEMBER')).toEqual([]);
  });
  it('never offers actions on yourself or, for an admin, on an owner', () => {
    expect(canActOnMember('OWNER', 'ADMIN', true)).toBe(false);
    expect(canActOnMember('ADMIN', 'OWNER', false)).toBe(false);
    expect(canActOnMember('ADMIN', 'MEMBER', false)).toBe(true);
    expect(canActOnMember('OWNER', 'OWNER', false)).toBe(true);
    expect(canActOnMember('MEMBER', 'MEMBER', false)).toBe(false);
  });
  it('offers departments in every team workspace, even before anyone else has joined', () => {
    expect(showDepartments('PERSONAL')).toBe(false);
    expect(showDepartments('TEAM')).toBe(true);
    expect(showDepartments(undefined)).toBe(true);
  });
  it('lets people edit themselves but not an owner, unless the actor is an owner', () => {
    expect(canEditProfile('MEMBER', 'MEMBER', true)).toBe(true);
    expect(canEditProfile('ADMIN', 'OWNER', false)).toBe(false);
    expect(canEditProfile('ADMIN', 'MEMBER', false)).toBe(true);
  });
  describe('filterMembers', () => {
    const base = { userId: '', email: '', employeeCode: null, jobTitle: null, role: 'MEMBER', status: 'ACTIVE',
      departmentId: null, departmentName: null, joinedAt: '' } as const;
    const list = [
      { ...base, userId: 'a', displayName: 'An Nguyen', email: 'an@x.com', employeeCode: 'E01', departmentId: 'd1' },
      { ...base, userId: 'b', displayName: 'Binh Tran', email: 'binh@x.com', role: 'ADMIN', status: 'SUSPENDED' },
    ] as unknown as MemberView[];
    const none = { q: '', role: '', status: '', departmentId: '' };
    it('searches name, email and employee code, ignoring case', () => {
      expect(filterMembers(list, { ...none, q: 'NGUYEN' }).map((m) => m.userId)).toEqual(['a']);
      expect(filterMembers(list, { ...none, q: 'binh@' }).map((m) => m.userId)).toEqual(['b']);
      expect(filterMembers(list, { ...none, q: 'e01' }).map((m) => m.userId)).toEqual(['a']);
    });
    it('ands the filters and can select people without a department', () => {
      expect(filterMembers(list, { ...none, role: 'ADMIN', status: 'SUSPENDED' }).map((m) => m.userId)).toEqual(['b']);
      expect(filterMembers(list, { ...none, departmentId: NO_DEPARTMENT }).map((m) => m.userId)).toEqual(['b']);
      expect(filterMembers(list, { ...none, departmentId: 'd1' }).map((m) => m.userId)).toEqual(['a']);
      expect(filterMembers(list, { ...none, role: 'ADMIN', departmentId: 'd1' })).toEqual([]);
    });
  });
  it('turns blank input into null', () => {
    expect(blankToNull('  ')).toBeNull();
    expect(blankToNull(' x ')).toBe('x');
  });
});

describe('documents layout (ADR-009)', () => {
  const none = { workspace: false, departmentId: null };
  it('gives the workspace publisher and an owner one Manage tab over everything', () => {
    expect(documentsLayout({ workspace: true, departmentId: null }, 'MEMBER')).toEqual({ manageAll: true, manageDepartmentId: null });
    expect(documentsLayout(none, 'OWNER').manageAll).toBe(true);
    expect(documentsTabs(documentsLayout(none, 'OWNER'), true)).toEqual(['manage', 'categories']);
  });
  it('gives a department publisher Manage for the department plus a read-only tab for everything', () => {
    const layout = documentsLayout({ workspace: false, departmentId: 'd1' }, 'MEMBER');
    expect(layout).toEqual({ manageAll: false, manageDepartmentId: 'd1' });
    expect(documentsTabs(layout, false)).toEqual(['manage', 'view']);
  });
  it('gives everyone else a read-only list, and managers the categories tab', () => {
    expect(documentsTabs(documentsLayout(none, 'MEMBER'), false)).toEqual(['view']);
    expect(documentsTabs(documentsLayout(none, 'ADMIN'), true)).toEqual(['view', 'categories']);
  });
  it('lets a person upload only where they publish; an owner who does not publish gets nothing', () => {
    expect(uploadScopes(none)).toEqual([]);
    expect(uploadScopes(undefined)).toEqual([]);
    expect(uploadScopes({ workspace: true, departmentId: null }).map((c) => c.scope)).toEqual([{ kind: 'WORKSPACE' }]);
    expect(uploadScopes({ workspace: false, departmentId: 'd1' }).map((c) => c.scope)).toEqual([{ kind: 'DEPARTMENT', departmentId: 'd1' }]);
    expect(uploadScopes({ workspace: true, departmentId: 'd1' })).toHaveLength(2);
  });
});
