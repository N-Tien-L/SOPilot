import { beforeEach, describe, expect, it } from 'vitest';
import { auditActionLabel, localToIso, summarizeDetails } from './audit';
import { clearInviteToken, holdInviteToken, peekInviteToken, readInviteToken } from './invite';
import { assignableRoles, blankToNull, canActOnMember, showDepartments } from './members';

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
  it('hides departments in personal and single-member workspaces', () => {
    expect(showDepartments('PERSONAL', 5)).toBe(false);
    expect(showDepartments('TEAM', 1)).toBe(false);
    expect(showDepartments('TEAM', 2)).toBe(true);
    expect(showDepartments('TEAM', null)).toBe(true);
  });
  it('turns blank input into null', () => {
    expect(blankToNull('  ')).toBeNull();
    expect(blankToNull(' x ')).toBe('x');
  });
});
