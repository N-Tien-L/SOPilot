'use client';

import { useState, type FormEvent } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, ConfirmDialog, EmptyState, Input, Modal, Select, Skeleton } from '@/components/ui';
import { reactivateMember, removeMember, suspendMember, updateMember } from '@/lib/api/endpoints';
import type { MemberView, WorkspaceRole } from '@/lib/api/types';
import { ROLE_LABEL, assignableRoles, blankToNull, canActOnMember, showDepartments } from '@/lib/admin/members';
import { useDepartments, useInvalidate, useMembers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { useAction } from './useAction';

type Pending = { kind: 'suspend' | 'reactivate' | 'remove'; member: MemberView };

function EditMemberDialog({
  member,
  actorRole,
  withDepartments,
  onClose,
}: {
  member: MemberView;
  actorRole: WorkspaceRole;
  withDepartments: boolean;
  onClose: () => void;
}) {
  const invalidate = useInvalidate();
  const departments = useDepartments(false, withDepartments);
  const { run, busy, error } = useAction();
  const [displayName, setDisplayName] = useState(member.displayName);
  const [employeeCode, setEmployeeCode] = useState(member.employeeCode ?? '');
  const [jobTitle, setJobTitle] = useState(member.jobTitle ?? '');
  const [departmentId, setDepartmentId] = useState(member.departmentId ?? '');
  const [role, setRole] = useState<WorkspaceRole>(member.role);
  const roles = assignableRoles(actorRole, member.role);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const patch: Parameters<typeof updateMember>[1] = {};
    if (displayName.trim() !== member.displayName) patch.displayName = displayName.trim();
    if (blankToNull(employeeCode) !== member.employeeCode) patch.employeeCode = blankToNull(employeeCode);
    if (blankToNull(jobTitle) !== member.jobTitle) patch.jobTitle = blankToNull(jobTitle);
    if (withDepartments && (departmentId || null) !== member.departmentId) patch.departmentId = departmentId || null;
    if (role !== member.role) patch.role = role;
    if (Object.keys(patch).length === 0) {
      onClose();
      return;
    }
    const ok = await run(() => updateMember(member.userId, patch));
    if (ok) {
      await invalidate('members');
      await invalidate('publishers');
      onClose();
    }
  }

  const departmentOptions = [
    { value: '', label: 'No department' },
    ...(departments.data ?? []).map((d) => ({ value: d.id, label: d.name })),
  ];
  // Keep an archived current department visible so the form does not silently drop it.
  if (member.departmentId && !departmentOptions.some((o) => o.value === member.departmentId)) {
    departmentOptions.push({ value: member.departmentId, label: `${member.departmentName ?? 'Department'} (archived)` });
  }

  return (
    <Modal open onClose={onClose} title="Edit member" description={member.email}>
      <form onSubmit={submit} className="space-y-3">
        <Input label="Full name" required maxLength={100} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        <Input label="Employee code" maxLength={50} value={employeeCode} onChange={(e) => setEmployeeCode(e.target.value)} />
        <Input label="Job title" maxLength={100} value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
        {withDepartments ? (
          <Select label="Department" options={departmentOptions} value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} />
        ) : null}
        {roles.length > 0 ? (
          <Select
            label="Role"
            options={roles.map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
            value={role}
            onChange={(e) => setRole(e.target.value as WorkspaceRole)}
            helperText="A role change ends the member's current sessions; they sign in again to get it."
          />
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={displayName.trim() === ''}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function MembersPanel() {
  const { data, isLoading, isError, error } = useMembers();
  const me = useSessionStore((s) => s.user);
  const workspace = useSessionStore((s) => s.workspace);
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState<MemberView | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const action = useAction();
  const actorRole = workspace?.role ?? 'MEMBER';
  const withDepartments = showDepartments(workspace?.kind, data ? data.length : null);

  if (isLoading) return <Skeleton count={4} height={40} />;
  if (isError) return <ErrorNote error={error} />;
  if (!data || data.length === 0) return <EmptyState title="No members" />;

  async function confirm() {
    if (!pending) return;
    const { kind, member } = pending;
    const call = kind === 'suspend' ? suspendMember : kind === 'reactivate' ? reactivateMember : removeMember;
    const ok = await action.run(() => call(member.userId));
    if (ok) {
      await invalidate('members');
      await invalidate('publishers');
      setPending(null);
    }
  }

  const copy: Record<Pending['kind'], { title: string; label: string; text: string }> = {
    suspend: {
      title: 'Suspend member',
      label: 'Suspend',
      text: 'They are signed out and cannot read anything in this workspace until reactivated.',
    },
    reactivate: { title: 'Reactivate member', label: 'Reactivate', text: 'They can sign in to this workspace again.' },
    remove: {
      title: 'Remove member',
      label: 'Remove',
      text: 'They lose access to this workspace. Documents they uploaded stay.',
    },
  };

  return (
    <>
      <div className="relative overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
          <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2">Name</th>
              <th scope="col" className="px-3 py-2">Employee ID</th>
              <th scope="col" className="px-3 py-2">Job title</th>
              {withDepartments ? <th scope="col" className="px-3 py-2">Department</th> : null}
              <th scope="col" className="px-3 py-2">Role</th>
              <th scope="col" className="px-3 py-2">Status</th>
              <th scope="col" className="px-3 py-2"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {data.map((m) => {
              const isSelf = m.userId === me?.id;
              const canAct = canActOnMember(actorRole, m.role, isSelf);
              const suspended = m.status !== 'ACTIVE';
              return (
                <tr key={m.userId} className="border-t border-border align-top">
                  <td className="px-3 py-2">
                    <div className="font-medium">
                      {m.displayName}
                      {isSelf ? <span className="ml-1 text-xs font-normal text-muted-foreground">(you)</span> : null}
                    </div>
                    <div className="text-xs text-muted-foreground">{m.email}</div>
                  </td>
                  <td className="px-3 py-2">{m.employeeCode ?? '-'}</td>
                  <td className="px-3 py-2">{m.jobTitle ?? '-'}</td>
                  {withDepartments ? <td className="px-3 py-2">{m.departmentName ?? '-'}</td> : null}
                  <td className="px-3 py-2">{ROLE_LABEL[m.role] ?? m.role}</td>
                  <td className="px-3 py-2">
                    <Badge variant={suspended ? 'warning' : 'success'}>{suspended ? 'Suspended' : 'Active'}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap justify-end gap-1">
                      {isSelf || canAct ? (
                        <Button size="sm" variant="ghost" onClick={() => setEditing(m)}>
                          Edit
                        </Button>
                      ) : null}
                      {canAct ? (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              action.reset();
                              setPending({ kind: suspended ? 'reactivate' : 'suspend', member: m });
                            }}
                          >
                            {suspended ? 'Reactivate' : 'Suspend'}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              action.reset();
                              setPending({ kind: 'remove', member: m });
                            }}
                          >
                            Remove
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {editing ? (
        <EditMemberDialog member={editing} actorRole={actorRole} withDepartments={withDepartments} onClose={() => setEditing(null)} />
      ) : null}
      {pending ? (
        <ConfirmDialog
          open
          onClose={() => setPending(null)}
          onConfirm={() => void confirm()}
          title={copy[pending.kind].title}
          confirmLabel={copy[pending.kind].label}
          variant={pending.kind === 'reactivate' ? 'info' : 'danger'}
          loading={action.busy}
          message={
            <>
              <strong>{pending.member.displayName}</strong>: {copy[pending.kind].text}
              {action.error ? <ErrorNote error={action.error} className="mt-2" /> : null}
            </>
          }
        />
      ) : null}
    </>
  );
}
