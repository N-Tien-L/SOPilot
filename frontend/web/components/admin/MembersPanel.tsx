'use client';

import { useState, type FormEvent } from 'react';
import { Search, ShieldCheck, UserCheck, Users } from 'lucide-react';
import { toast } from 'sonner';
import { ErrorNote } from '@/components/app/ErrorNote';
import { CountUp } from '@/components/effects';
import { Avatar, Badge, Button, Checkbox, ConfirmDialog, EmptyState, Input, Modal, Select, Skeleton, StatCard } from '@/components/ui';
import { reactivateMember, removeMember, suspendMember, updateMember } from '@/lib/api/endpoints';
import type { MemberView, WorkspaceRole } from '@/lib/api/types';
import {
  NO_DEPARTMENT,
  ROLE_LABEL,
  assignableRoles,
  blankToNull,
  canActOnMember,
  canEditProfile,
  filterMembers,
  showDepartments,
  type MemberFilters,
} from '@/lib/admin/members';
import { useDepartments, useInvalidate, useMembers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { moveMembers } from './moveMembers';
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
      toast.success('Member updated');
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

const NO_FILTERS: MemberFilters = { q: '', role: '', status: '', departmentId: '' };

export function MembersPanel() {
  const { data, isLoading, isError, error } = useMembers();
  const me = useSessionStore((s) => s.user);
  const workspace = useSessionStore((s) => s.workspace);
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState<MemberView | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [filters, setFilters] = useState<MemberFilters>(NO_FILTERS);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [target, setTarget] = useState('');
  const [moveNote, setMoveNote] = useState<{ moved: number; failed: number } | null>(null);
  const action = useAction();
  const bulk = useAction();
  const actorRole = workspace?.role ?? 'MEMBER';
  const withDepartments = showDepartments(workspace?.kind);
  const departments = useDepartments(false, withDepartments);

  if (isLoading) return <Skeleton count={4} height={40} />;
  if (isError) return <ErrorNote error={error} />;
  if (!data || data.length === 0) return <EmptyState title="No members" />;

  const rows = filterMembers(data, filters);
  const editable = rows.filter((m) => canEditProfile(actorRole, m.role, m.userId === me?.id));
  const allShownSelected = editable.length > 0 && editable.every((m) => selected.has(m.userId));
  const filtered = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);
  const set = (key: keyof MemberFilters) => (value: string) => setFilters((f) => ({ ...f, [key]: value }));

  function toggle(userId: string, on: boolean) {
    setSelected((cur) => {
      const next = new Set(cur);
      if (on) next.add(userId);
      else next.delete(userId);
      return next;
    });
  }
  function toggleAllShown(on: boolean) {
    setSelected((cur) => {
      const next = new Set(cur);
      for (const m of editable) {
        if (on) next.add(m.userId);
        else next.delete(m.userId);
      }
      return next;
    });
  }

  async function moveSelected() {
    const ids = [...selected];
    setMoveNote(null);
    const box: { done: Awaited<ReturnType<typeof moveMembers>> | null } = { done: null };
    await bulk.run(async () => {
      box.done = await moveMembers(ids, target === NO_DEPARTMENT ? null : target);
    });
    const done = box.done;
    if (!done) return;
    await invalidate('members');
    await invalidate('publishers');
    await invalidate('departments');
    await invalidate('member-me');
    setMoveNote({ moved: done.moved.length, failed: done.failed.length });
    // Keep the people that could not be moved selected so the action can be repeated for them.
    setSelected(new Set(done.failed.map((f) => f.userId)));
    if (done.failed.length === 0) setTarget('');
  }

  async function confirm() {
    if (!pending) return;
    const { kind, member } = pending;
    const call = kind === 'suspend' ? suspendMember : kind === 'reactivate' ? reactivateMember : removeMember;
    const ok = await action.run(() => call(member.userId));
    if (ok) {
      await invalidate('members');
      await invalidate('publishers');
      setSelected((cur) => {
        const next = new Set(cur);
        next.delete(member.userId);
        return next;
      });
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

  // The same buttons for the table row (desktop) and the card (phone). One line, never wrapped.
  function actionButtons(m: MemberView) {
    const isSelf = m.userId === me?.id;
    const canAct = canActOnMember(actorRole, m.role, isSelf);
    const mayEdit = canEditProfile(actorRole, m.role, isSelf);
    const suspended = m.status !== 'ACTIVE';
    if (!mayEdit && !canAct) return null;
    return (
      <div className="flex flex-nowrap justify-end gap-1 whitespace-nowrap">
        {mayEdit ? (
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
    );
  }

  const departmentOptions = [
    { value: NO_DEPARTMENT, label: 'No department' },
    ...(departments.data ?? []).map((d) => ({ value: d.id, label: d.name })),
  ];

  const activeCount = data.filter((m) => m.status === 'ACTIVE').length;
  const suspendedCount = data.length - activeCount;
  const adminCount = data.filter((m) => m.role === 'OWNER' || m.role === 'ADMIN').length;

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Total members"
          value={<CountUp to={data.length} />}
          hint={withDepartments && departments.data ? `Across ${departments.data.length} departments` : 'In this workspace'}
          icon={<Users size={14} aria-hidden />}
        />
        <StatCard
          label="Active"
          value={<CountUp to={activeCount} />}
          hint={suspendedCount > 0 ? `${suspendedCount} suspended` : 'All members active'}
          icon={<UserCheck size={14} aria-hidden />}
        />
        <StatCard
          label="Owners & admins"
          value={<CountUp to={adminCount} />}
          hint="Workspace managers"
          icon={<ShieldCheck size={14} aria-hidden />}
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card p-3 shadow-[var(--shadow-sm)]">
        <div className="relative min-w-[200px] flex-1">
          <Search size={14} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            aria-label="Search members"
            placeholder="Search name, email or employee ID"
            value={filters.q}
            onChange={(e) => set('q')(e.target.value)}
            className="h-10 w-full rounded-xl border border-input bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-placeholder outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
          />
        </div>
        <div className="w-36">
          <Select
            aria-label="Role"
            placeholder="All roles"
            allowEmpty
            options={(Object.keys(ROLE_LABEL) as WorkspaceRole[]).map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
            value={filters.role}
            onChange={(e) => set('role')(e.target.value)}
          />
        </div>
        <div className="w-40">
          <Select
            aria-label="Status"
            placeholder="All statuses"
            allowEmpty
            options={[
              { value: 'ACTIVE', label: 'Active' },
              { value: 'SUSPENDED', label: 'Suspended' },
            ]}
            value={filters.status}
            onChange={(e) => set('status')(e.target.value)}
          />
        </div>
        {withDepartments ? (
          <div className="w-52">
            <Select
              aria-label="Department"
              placeholder="All departments"
              allowEmpty
              options={departmentOptions}
              value={filters.departmentId}
              onChange={(e) => set('departmentId')(e.target.value)}
            />
          </div>
        ) : null}
        {filtered ? (
          <Button size="sm" variant="ghost" onClick={() => setFilters(NO_FILTERS)}>
            Clear filters
          </Button>
        ) : null}
        <span role="status" className="text-xs font-medium text-muted-foreground">
          {filtered
            ? `${rows.length} of ${data.length} ${data.length === 1 ? 'member' : 'members'}`
            : `${data.length} ${data.length === 1 ? 'member' : 'members'}`}
        </span>
      </div>

      {selected.size > 0 ? (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-primary/35 bg-primary-soft/50 p-3.5 text-sm">
          <span className="font-semibold text-primary-strong">{selected.size} selected</span>
          {withDepartments ? (
            <>
              <div className="w-56">
                <Select
                  aria-label="Move selected to department"
                  placeholder="Move to department"
                  options={departmentOptions}
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                />
              </div>
              <Button size="sm" variant="primary" disabled={target === ''} loading={bulk.busy} onClick={() => void moveSelected()}>
                Move
              </Button>
            </>
          ) : null}
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
            Clear selection
          </Button>
          <span className="text-xs text-muted-foreground">
            A person is in one department, so moving leaves the old one and ends any publisher role there.
          </span>
        </div>
      ) : null}
      {moveNote ? (
        <p role="status" className={`mb-3 text-sm ${moveNote.failed > 0 ? 'text-warning-foreground' : 'text-success-foreground'}`}>
          {moveNote.moved} moved{moveNote.failed > 0 ? `, ${moveNote.failed} could not be moved and stay selected` : ''}.
        </p>
      ) : null}
      {bulk.error ? <ErrorNote error={bulk.error} className="mb-3" /> : null}

      {rows.length === 0 ? (
        <EmptyState title="No members match" description="Change the search or clear the filters." />
      ) : (
        <div className="relative hidden overflow-x-auto rounded-2xl border border-border bg-card shadow-[var(--shadow-sm)] md:block">
          <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/60 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="w-10 px-4 py-3">
                  <Checkbox
                    aria-label="Select all shown"
                    checked={allShownSelected}
                    disabled={editable.length === 0}
                    onChange={(e) => toggleAllShown(e.target.checked)}
                  />
                </th>
                <th scope="col" className="px-4 py-3">Name</th>
                <th scope="col" className="px-4 py-3">Employee ID</th>
                <th scope="col" className="px-4 py-3">Job title</th>
                {withDepartments ? <th scope="col" className="px-4 py-3">Department</th> : null}
                <th scope="col" className="px-4 py-3">Role</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {rows.map((m) => {
                const isSelf = m.userId === me?.id;
                const mayEdit = canEditProfile(actorRole, m.role, isSelf);
                const suspended = m.status !== 'ACTIVE';
                return (
                  <tr key={m.userId} className="align-top transition-colors hover:bg-muted/35">
                    <td className="px-4 py-3">
                      {mayEdit ? (
                        <Checkbox
                          aria-label={`Select ${m.displayName}`}
                          checked={selected.has(m.userId)}
                          onChange={(e) => toggle(m.userId, e.target.checked)}
                        />
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={m.displayName} size="sm" />
                        <div className="min-w-0">
                          <div className="font-semibold text-foreground">
                            {m.displayName}
                            {isSelf ? <span className="ml-1 text-xs font-normal text-muted-foreground">(you)</span> : null}
                          </div>
                          <div className="text-xs text-muted-foreground">{m.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{m.employeeCode ?? '-'}</td>
                    <td className="px-4 py-3 text-foreground">{m.jobTitle ?? '-'}</td>
                    {withDepartments ? <td className="px-4 py-3 text-foreground">{m.departmentName ?? '-'}</td> : null}
                    <td className="px-4 py-3">
                      <Badge variant={m.role === 'OWNER' ? 'default' : m.role === 'ADMIN' ? 'info' : 'neutral'}>
                        {ROLE_LABEL[m.role] ?? m.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={suspended ? 'warning' : 'success'}>{suspended ? 'Suspended' : 'Active'}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      {actionButtons(m)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > 0 ? (
        <ul className="space-y-3 md:hidden" aria-label="Members">
          {rows.map((m) => {
            const isSelf = m.userId === me?.id;
            const mayEdit = canEditProfile(actorRole, m.role, isSelf);
            const suspended = m.status !== 'ACTIVE';
            return (
              <li key={m.userId} className="rounded-2xl border border-border bg-card p-4 text-sm shadow-[var(--shadow-sm)]">
                <div className="flex items-start gap-3">
                  {mayEdit ? (
                    <Checkbox
                      aria-label={`Select ${m.displayName}`}
                      checked={selected.has(m.userId)}
                      onChange={(e) => toggle(m.userId, e.target.checked)}
                    />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">
                      {m.displayName}
                      {isSelf ? <span className="ml-1 text-xs font-normal text-muted-foreground">(you)</span> : null}
                    </div>
                    <div className="break-all text-xs text-muted-foreground">{m.email}</div>
                  </div>
                  <Badge variant={suspended ? 'warning' : 'success'}>{suspended ? 'Suspended' : 'Active'}</Badge>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted-foreground">Role</dt>
                  <dd>{ROLE_LABEL[m.role] ?? m.role}</dd>
                  {withDepartments ? (
                    <>
                      <dt className="text-muted-foreground">Department</dt>
                      <dd>{m.departmentName ?? '-'}</dd>
                    </>
                  ) : null}
                  {m.employeeCode ? (
                    <>
                      <dt className="text-muted-foreground">Employee ID</dt>
                      <dd>{m.employeeCode}</dd>
                    </>
                  ) : null}
                  {m.jobTitle ? (
                    <>
                      <dt className="text-muted-foreground">Job title</dt>
                      <dd>{m.jobTitle}</dd>
                    </>
                  ) : null}
                </dl>
                <div className="mt-2">{actionButtons(m)}</div>
              </li>
            );
          })}
        </ul>
      ) : null}
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
