'use client';

import { useState } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Button, EmptyState, Select, Skeleton } from '@/components/ui';
import {
  assignDepartmentPublisher,
  assignWorkspacePublisher,
  unassignDepartmentPublisher,
  unassignWorkspacePublisher,
} from '@/lib/api/endpoints';
import { showDepartments } from '@/lib/admin/members';
import { useInvalidate, useMembers, usePublishers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { useAction } from './useAction';

/** One scope (the whole workspace or one department) with its publisher and a picker. */
function PublisherRow({
  label,
  hint,
  publisherName,
  candidates,
  onAssign,
  onClear,
}: {
  label: string;
  hint: string;
  publisherName: string | null;
  candidates: { value: string; label: string }[];
  onAssign: (userId: string) => Promise<unknown>;
  onClear: () => Promise<unknown>;
}) {
  const invalidate = useInvalidate();
  const { run, busy, error } = useAction();
  const [userId, setUserId] = useState('');

  async function assign() {
    if (await run(() => onAssign(userId))) {
      setUserId('');
      await invalidate('publishers');
      await invalidate('member-me');
    }
  }
  async function clear() {
    if (await run(onClear)) {
      await invalidate('publishers');
      await invalidate('member-me');
    }
  }

  return (
    <li className="px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-medium">{label}</div>
          <div className="text-xs text-muted-foreground">{hint}</div>
          <div className="mt-1 text-sm">
            Publisher: {publisherName ? <strong>{publisherName}</strong> : <span className="text-muted-foreground">none</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-56">
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
      </div>
      {error ? <ErrorNote error={error} className="mt-2" /> : null}
    </li>
  );
}

/** OWNER only (ADR-009): who may publish for the workspace and for each department. */
export function PublishersPanel() {
  const workspace = useSessionStore((s) => s.workspace);
  const overview = usePublishers();
  const members = useMembers();

  if (overview.isLoading || members.isLoading) return <Skeleton count={3} height={64} />;
  if (overview.isError) return <ErrorNote error={overview.error} />;
  if (members.isError) return <ErrorNote error={members.error} />;
  if (!overview.data) return <EmptyState title="No publisher data" />;

  const active = (members.data ?? []).filter((m) => m.status === 'ACTIVE');
  const option = (m: (typeof active)[number]) => ({ value: m.userId, label: `${m.displayName} (${m.email})` });
  const candidates = active.map(option);
  const withDepartments = showDepartments(workspace?.kind, members.data ? members.data.length : null);
  const departments = withDepartments ? overview.data.departments : [];

  return (
    <>
      <p className="mb-3 text-sm text-muted-foreground">
        A publisher uploads and manages documents for a scope. Owners and admins do not publish unless assigned. A department publisher must belong to that department.
      </p>
      <ul className="divide-y divide-border rounded-lg border border-border bg-card text-sm">
        <PublisherRow
          label="Whole workspace"
          hint="Documents visible to everyone in the workspace."
          publisherName={overview.data.workspace?.displayName ?? null}
          candidates={candidates}
          onAssign={assignWorkspacePublisher}
          onClear={unassignWorkspacePublisher}
        />
        {departments.map((d) => (
          <PublisherRow
            key={d.departmentId}
            label={d.name}
            hint="Documents limited to this department."
            publisherName={d.publisher?.displayName ?? null}
            candidates={active.filter((m) => m.departmentId === d.departmentId).map(option)}
            onAssign={(userId) => assignDepartmentPublisher(d.departmentId, userId)}
            onClear={() => unassignDepartmentPublisher(d.departmentId)}
          />
        ))}
      </ul>
    </>
  );
}
