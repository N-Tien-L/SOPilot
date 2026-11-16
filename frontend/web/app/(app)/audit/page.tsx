'use client';

import { useMemo, useState } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Button, EmptyState, Select, Skeleton } from '@/components/ui';
import { AUDIT_ACTIONS, auditActionLabel, localToIso, summarizeDetails } from '@/lib/admin/audit';
import { useAuditLogs, useMembers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';

function AuditLog() {
  const [action, setAction] = useState('');
  const [actorId, setActorId] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const members = useMembers();
  const logs = useAuditLogs({
    ...(action ? { action } : {}),
    ...(actorId ? { actorId } : {}),
    ...(localToIso(from) ? { from: localToIso(from) } : {}),
    ...(localToIso(to) ? { to: localToIso(to) } : {}),
  });
  const names = useMemo(() => new Map((members.data ?? []).map((m) => [m.userId, m.displayName])), [members.data]);
  const rows = logs.data?.pages.flatMap((p) => p.data) ?? [];

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Audit log</h1>
      <p className="mt-1 text-sm text-muted-foreground">Who changed what in this workspace, newest first. Only owners can read it.</p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="w-56">
          <Select
            aria-label="Action"
            placeholder="All actions"
            options={AUDIT_ACTIONS.map((a) => ({ value: a.value, label: a.label }))}
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>
        <div className="w-52">
          <Select
            aria-label="Actor"
            placeholder="Anyone"
            options={(members.data ?? []).map((m) => ({ value: m.userId, label: m.displayName }))}
            value={actorId}
            onChange={(e) => setActorId(e.target.value)}
          />
        </div>
        <label className="text-xs text-muted-foreground">
          From
          <input
            type="datetime-local"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="mt-1 block h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          To
          <input
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="mt-1 block h-10 rounded-md border border-input bg-card px-3 text-sm text-foreground"
          />
        </label>
        {action || actorId || from || to ? (
          <Button
            variant="ghost"
            onClick={() => {
              setAction('');
              setActorId('');
              setFrom('');
              setTo('');
            }}
          >
            Clear filters
          </Button>
        ) : null}
      </div>

      {logs.isLoading ? <div className="mt-4"><Skeleton count={5} height={40} /></div> : null}
      {logs.isError ? <ErrorNote error={logs.error} className="mt-4" /> : null}
      {logs.data && rows.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="No entries" description="Nothing matches these filters." />
        </div>
      ) : null}
      {rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">When</th>
                <th scope="col" className="px-3 py-2">Actor</th>
                <th scope="col" className="px-3 py-2">Action</th>
                <th scope="col" className="px-3 py-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-3 py-2">{new Date(e.createdAt).toLocaleString()}</td>
                  <td className="px-3 py-2">{e.actorId ? (names.get(e.actorId) ?? 'Former member') : 'System'}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{auditActionLabel(e.action)}</div>
                    {e.targetType ? <div className="text-xs text-muted-foreground">{e.targetType.toLowerCase()}</div> : null}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground [overflow-wrap:anywhere]">{summarizeDetails(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {logs.hasNextPage ? (
        <div className="mt-4">
          <Button variant="outline" loading={logs.isFetchingNextPage} onClick={() => void logs.fetchNextPage()}>
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default function AuditPage() {
  const role = useSessionStore((s) => s.workspace?.role);
  if (role !== 'OWNER') {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners only" description="The audit log is visible to workspace owners." />
      </div>
    );
  }
  return <AuditLog />;
}
