'use client';

import { useState } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, EmptyState, Skeleton } from '@/components/ui';
import { useInvitations, useMembers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';

function daysLeft(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

function Members() {
  const { data, isLoading, isError, error } = useMembers();
  if (isLoading) return <Skeleton count={4} height={40} />;
  if (isError) return <ErrorNote error={error} />;
  if (!data || data.length === 0) return <EmptyState title="No members" />;
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
        <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Name</th>
            <th scope="col" className="px-3 py-2">Email</th>
            <th scope="col" className="px-3 py-2">Employee ID</th>
            <th scope="col" className="px-3 py-2">Job title</th>
            <th scope="col" className="px-3 py-2">Department</th>
            <th scope="col" className="px-3 py-2">Role</th>
            <th scope="col" className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.map((m) => (
            <tr key={m.userId} className="border-t border-border">
              <td className="px-3 py-2 font-medium">{m.displayName}</td>
              <td className="px-3 py-2">{m.email}</td>
              <td className="px-3 py-2">{m.employeeCode ?? '-'}</td>
              <td className="px-3 py-2">{m.jobTitle ?? '-'}</td>
              <td className="px-3 py-2">{m.departmentName ?? '-'}</td>
              <td className="px-3 py-2">{m.role}</td>
              <td className="px-3 py-2">
                <Badge variant={m.status === 'ACTIVE' ? 'success' : 'neutral'}>{m.status === 'ACTIVE' ? 'Active' : 'Suspended'}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Invitations() {
  const { data, isLoading, isError, error } = useInvitations();
  if (isLoading) return <Skeleton count={3} height={40} />;
  if (isError) return <ErrorNote error={error} />;
  if (!data || data.length === 0) return <EmptyState title="No pending invitations" />;
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
        <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Email</th>
            <th scope="col" className="px-3 py-2">Role</th>
            <th scope="col" className="px-3 py-2">Department</th>
            <th scope="col" className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.map((i) => {
            const left = daysLeft(i.expiresAt);
            return (
              <tr key={i.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">{i.email}</td>
                <td className="px-3 py-2">{i.role}</td>
                <td className="px-3 py-2">{i.departmentName ?? '-'}</td>
                <td className="px-3 py-2">
                  {left > 0 ? <Badge variant="info">Pending, {left}d left</Badge> : <Badge variant="neutral">Expired</Badge>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function MembersPage() {
  const role = useSessionStore((s) => s.workspace?.role);
  const [tab, setTab] = useState<'members' | 'invitations'>('members');

  if (role !== 'OWNER' && role !== 'ADMIN') {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners and admins only" description="Ask a workspace owner or admin if you need to see who is in this workspace." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Members</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Read-only for now. Inviting, editing and suspending members arrive with ticket V2-33.
      </p>
      <div role="tablist" aria-label="Members and invitations" className="mt-4 flex gap-1 border-b border-border">
        {(['members', 'invitations'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab === t ? 'border-b-2 border-primary font-semibold text-primary-strong' : 'text-muted-foreground'}`}
          >
            {t === 'members' ? 'Members' : 'Invitations'}
          </button>
        ))}
      </div>
      <div className="mt-4">{tab === 'members' ? <Members /> : <Invitations />}</div>
    </div>
  );
}
