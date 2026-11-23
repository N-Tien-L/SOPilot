'use client';

import { useState, type FormEvent } from 'react';
import { Plus } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, Checkbox, ConfirmDialog, EmptyState, Input, Modal, Select, Skeleton } from '@/components/ui';
import {
  assignDepartmentPublisher,
  assignWorkspacePublisher,
  createDepartment,
  deleteDepartment,
  unassignDepartmentPublisher,
  unassignWorkspacePublisher,
  updateDepartment,
} from '@/lib/api/endpoints';
import type { DepartmentView, MemberView, WorkspaceRole } from '@/lib/api/types';
import { canEditProfile } from '@/lib/admin/members';
import { useDepartments, useInvalidate, useMembers, usePublishers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { moveMembers } from './moveMembers';
import { NameDialog } from './NamedListPanel';
import { useAction } from './useAction';

/** Everything a department change can affect: lists, member profiles, publishers, invitations, the caller's rights. */
const REFRESH = ['departments', 'members', 'publishers', 'invitations', 'member-me'] as const;

function memberOption(m: MemberView) {
  return {
    value: m.userId,
    label: `${m.displayName} (${m.email})${m.departmentName ? ` · now in ${m.departmentName}` : ''}`,
  };
}

/** A publisher picker with Assign/Change and Remove. Read-only text when the caller may not change it. */
function PublisherControl({
  label,
  publisherName,
  candidates,
  canEdit,
  noCandidatesHint,
  onAssign,
  onClear,
}: {
  label: string;
  publisherName: string | null;
  candidates: { value: string; label: string }[];
  canEdit: boolean;
  noCandidatesHint?: string;
  onAssign: (userId: string) => Promise<unknown>;
  onClear: () => Promise<unknown>;
}) {
  const refresh = useInvalidate();
  const { run, busy, error } = useAction();
  const [userId, setUserId] = useState('');

  async function after() {
    for (const key of REFRESH) await refresh(key);
  }
  async function assign() {
    if (await run(() => onAssign(userId))) {
      setUserId('');
      await after();
    }
  }
  async function clear() {
    if (await run(onClear)) await after();
  }

  const current = publisherName ? <strong>{publisherName}</strong> : <span className="text-muted-foreground">none</span>;
  if (!canEdit) return <div className="text-sm">Publisher: {current}</div>;

  return (
    <div>
      <div className="text-sm">Publisher: {current}</div>
      {candidates.length === 0 && noCandidatesHint ? (
        <p className="mt-1 text-xs text-muted-foreground">{noCandidatesHint}</p>
      ) : (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="w-64">
            <Select
              aria-label={`Publisher for ${label}`}
              placeholder="Choose a member"
              options={candidates}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
          <Button variant="primary" size="sm" disabled={userId === ''} loading={busy} onClick={() => void assign()}>
            {publisherName ? 'Change' : 'Assign'}
          </Button>
          {publisherName ? (
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void clear()}>
              Remove
            </Button>
          ) : null}
        </div>
      )}
      {error ? <ErrorNote error={error} className="mt-2" /> : null}
    </div>
  );
}

/**
 * New department: a name, the people who belong to it (search + select several) and, optionally, which
 * of them publishes. A person is in one department, so choosing someone moves them out of their current
 * one; the dialog says how many are affected. The publisher must be one of the chosen people because
 * the server accepts only a member of the department.
 */
function CreateDialog({
  members,
  actorRole,
  selfId,
  canPickPublisher,
  onClose,
  onCreate,
}: {
  members: MemberView[];
  actorRole: WorkspaceRole;
  selfId: string | undefined;
  canPickPublisher: boolean;
  onClose: () => void;
  onCreate: (name: string, memberIds: string[], publisherId: string | null) => Promise<void>;
}) {
  const { run, busy, error } = useAction();
  const [name, setName] = useState('');
  const [q, setQ] = useState('');
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [publisherId, setPublisherId] = useState('');

  const eligible = members.filter((m) => canEditProfile(actorRole, m.role, m.userId === selfId));
  const needle = q.trim().toLowerCase();
  const shown = eligible.filter(
    (m) => !needle || [m.displayName, m.email, m.employeeCode ?? ''].some((v) => v.toLowerCase().includes(needle)),
  );
  const picked = eligible.filter((m) => chosen.has(m.userId));
  const leaving = picked.filter((m) => m.departmentId !== null).length;
  const publisher = chosen.has(publisherId) ? publisherId : '';
  const allShown = shown.length > 0 && shown.every((m) => chosen.has(m.userId));

  function toggle(userId: string, on: boolean) {
    setChosen((cur) => {
      const next = new Set(cur);
      if (on) next.add(userId);
      else next.delete(userId);
      return next;
    });
  }
  function toggleShown(on: boolean) {
    setChosen((cur) => {
      const next = new Set(cur);
      for (const m of shown) {
        if (on) next.add(m.userId);
        else next.delete(m.userId);
      }
      return next;
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await run(() => onCreate(name.trim(), picked.map((m) => m.userId), publisher || null))) onClose();
  }

  return (
    <Modal open onClose={onClose} title="New department" size="lg">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Name" required maxLength={100} autoFocus value={name} onChange={(e) => setName(e.target.value)} />

        <fieldset className="min-w-0 space-y-2 border-0 p-0">
          <legend className="text-sm font-medium">People in this department (optional)</legend>
          <div className="flex flex-wrap items-center gap-2">
            <input
              aria-label="Search people"
              placeholder="Search name, email or employee ID"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-10 w-72 rounded-md border border-input bg-card px-3 text-sm"
            />
            <Button type="button" size="sm" variant="outline" disabled={shown.length === 0 || allShown} onClick={() => toggleShown(true)}>
              Select all shown
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={chosen.size === 0} onClick={() => setChosen(new Set())}>
              Clear
            </Button>
            <span role="status" className="text-sm text-muted-foreground">{chosen.size} selected</span>
          </div>
          <ul className="max-h-64 divide-y divide-border overflow-y-auto rounded-md border border-border">
            {shown.map((m) => (
              <li key={m.userId} className="px-3 py-2">
                <Checkbox
                  label={m.displayName}
                  description={`${m.email}${m.departmentName ? ` · now in ${m.departmentName}` : ' · no department'}`}
                  checked={chosen.has(m.userId)}
                  onChange={(e) => toggle(m.userId, e.target.checked)}
                />
              </li>
            ))}
            {shown.length === 0 ? (
              <li className="px-3 py-3 text-sm text-muted-foreground">
                {eligible.length === 0 ? 'No one you can move yet.' : 'No one matches this search.'}
              </li>
            ) : null}
          </ul>
          {leaving > 0 ? (
            <p className="text-xs text-muted-foreground">
              {leaving} selected {leaving === 1 ? 'person leaves' : 'people leave'} their current department, and any publisher role held
              there ends.
            </p>
          ) : null}
        </fieldset>

        {canPickPublisher ? (
          <Select
            label="Publisher (optional)"
            placeholder={picked.length === 0 ? 'Select people first' : 'No publisher yet'}
            allowEmpty
            disabled={picked.length === 0}
            options={picked.map((m) => ({ value: m.userId, label: `${m.displayName} (${m.email})` }))}
            value={publisher}
            onChange={(e) => setPublisherId(e.target.value)}
            helperText="The publisher uploads and manages documents of this department. You can set it later."
          />
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={name.trim() === ''}>
            {picked.length > 0 ? `Create and add ${picked.length}` : 'Create'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/**
 * Departments and who publishes for each one (ADR-009), in one place. Everyone in OWNER/ADMIN sees
 * it; only the OWNER assigns publishers.
 */
export function DepartmentsPanel() {
  const role = useSessionStore((s) => s.workspace?.role);
  const selfId = useSessionStore((s) => s.user?.id);
  const isOwner = role === 'OWNER';
  const refresh = useInvalidate();
  const departments = useDepartments(true);
  const overview = usePublishers();
  const members = useMembers();
  const action = useAction();
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<DepartmentView | null>(null);
  const [deleting, setDeleting] = useState<DepartmentView | null>(null);
  // The department exists once created; steps after that report here instead of failing the dialog.
  const [notice, setNotice] = useState<{ name: string; moveFailed: number; publisherError: unknown } | null>(null);

  if (departments.isLoading || overview.isLoading || members.isLoading) return <Skeleton count={3} height={64} />;
  if (departments.isError) return <ErrorNote error={departments.error} />;
  if (overview.isError) return <ErrorNote error={overview.error} />;
  if (members.isError) return <ErrorNote error={members.error} />;

  const active = (members.data ?? []).filter((m) => m.status === 'ACTIVE');
  const publisherOf = new Map((overview.data?.departments ?? []).map((d) => [d.departmentId, d.publisher?.displayName ?? null]));

  async function after() {
    for (const key of REFRESH) await refresh(key);
  }

  async function create(name: string, memberIds: string[], publisherId: string | null) {
    const created = await createDepartment(name);
    let moveFailed = 0;
    let publisherError: unknown = null;
    try {
      const moved = memberIds.length > 0 ? await moveMembers(memberIds, created.id) : { moved: [], failed: [] };
      moveFailed = moved.failed.length;
      const publisherMoved = publisherId !== null && !moved.failed.some((f) => f.userId === publisherId);
      if (publisherId !== null && publisherMoved) {
        await assignDepartmentPublisher(created.id, publisherId);
      } else if (publisherId !== null) {
        publisherError = new Error('The chosen publisher could not be moved into the department.');
      }
    } catch (e) {
      publisherError = e;
    } finally {
      await after();
    }
    if (moveFailed > 0 || publisherError) setNotice({ name, moveFailed, publisherError });
  }

  async function toggleArchive(d: DepartmentView) {
    const next = d.status === 'ARCHIVED' ? 'ACTIVE' : 'ARCHIVED';
    if (await action.run(() => updateDepartment(d.id, { status: next }))) await after();
  }

  async function confirmDelete() {
    if (!deleting) return;
    if (await action.run(() => deleteDepartment(deleting.id))) {
      await after();
      setDeleting(null);
    }
  }

  const list = departments.data ?? [];

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          A publisher uploads and manages the documents of a department. Owners and admins do not publish unless assigned, and a
          publisher must belong to the department.
        </p>
        <Button variant="primary" icon={<Plus size={16} aria-hidden />} onClick={() => { setNotice(null); setCreating(true); }}>
          New department
        </Button>
      </div>
      {action.error && !deleting ? <ErrorNote error={action.error} className="mb-2" /> : null}
      {notice ? (
        <div role="alert" className="mb-3 rounded-md bg-warning-soft p-3 text-sm text-warning-foreground">
          Department <strong>{notice.name}</strong> was created.
          {notice.moveFailed > 0 ? ` ${notice.moveFailed} ${notice.moveFailed === 1 ? 'person' : 'people'} could not be added; add them under Members.` : ''}
          {notice.publisherError ? ' Its publisher could not be set; assign one below.' : ''}
          {notice.publisherError ? <ErrorNote error={notice.publisherError} className="mt-2" /> : null}
        </div>
      ) : null}

      <ul className="divide-y divide-border rounded-lg border border-border bg-card text-sm">
        <li className="px-3 py-3">
          <div className="font-medium">Whole workspace</div>
          <div className="mb-2 text-xs text-muted-foreground">Documents visible to everyone in the workspace.</div>
          <PublisherControl
            label="the whole workspace"
            publisherName={overview.data?.workspace?.displayName ?? null}
            candidates={active.map(memberOption)}
            canEdit={isOwner}
            onAssign={assignWorkspacePublisher}
            onClear={unassignWorkspacePublisher}
          />
        </li>
        {list.map((d) => {
          const archived = d.status === 'ARCHIVED';
          const people = active.filter((m) => m.departmentId === d.id);
          return (
            <li key={d.id} className="px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={archived ? 'text-muted-foreground' : 'font-medium'}>{d.name}</span>
                    {archived ? <Badge variant="neutral">Archived</Badge> : null}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {people.length} member{people.length === 1 ? '' : 's'} · documents limited to this department
                  </div>
                </div>
                <span className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => setRenaming(d)}>
                    Rename
                  </Button>
                  <Button size="sm" variant="ghost" disabled={action.busy} onClick={() => void toggleArchive(d)}>
                    {archived ? 'Restore' : 'Archive'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => { action.reset(); setDeleting(d); }}>
                    Delete
                  </Button>
                </span>
              </div>
              {archived ? null : (
                <div className="mt-2">
                  <PublisherControl
                    label={d.name}
                    publisherName={publisherOf.get(d.id) ?? null}
                    candidates={people.map(memberOption)}
                    canEdit={isOwner}
                    noCandidatesHint="No one is in this department yet. Add people on the Members page (select several, then Move), then pick a publisher here."
                    onAssign={(userId) => assignDepartmentPublisher(d.id, userId)}
                    onClear={() => unassignDepartmentPublisher(d.id)}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {list.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No departments yet" description="Departments group members and can limit who reads a document." />
        </div>
      ) : null}

      {creating ? (
        <CreateDialog
          members={active}
          actorRole={role ?? 'MEMBER'}
          selfId={selfId}
          canPickPublisher={isOwner}
          onClose={() => setCreating(false)}
          onCreate={create}
        />
      ) : null}
      {renaming ? (
        <NameDialog
          title="Rename department"
          initial={renaming.name}
          submitLabel="Save"
          onSubmit={async (name) => {
            await updateDepartment(renaming.id, { name });
            await after();
          }}
          onClose={() => setRenaming(null)}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          open
          onClose={() => setDeleting(null)}
          onConfirm={() => void confirmDelete()}
          title="Delete department"
          confirmLabel="Delete"
          variant="danger"
          loading={action.busy}
          message={
            <>
              Delete <strong>{deleting.name}</strong>? This works only while nothing uses it; otherwise archive it instead.
              {action.error ? <ErrorNote error={action.error} className="mt-2" /> : null}
            </>
          }
        />
      ) : null}
    </>
  );
}
