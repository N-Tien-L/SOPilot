'use client';

import { useMemo, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { FadeIn } from '@/components/motion/Primitives';
import { Button, EmptyState, PageHeader, Select, Skeleton } from '@/components/ui';
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
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <FadeIn>
        <PageHeader
          title="Audit log"
          description="Who changed what in this workspace, newest first. Only owners can read it."
        />
      </FadeIn>

      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-card p-3.5 shadow-[var(--shadow-sm)]">
        <div className="w-56">
          <Select
            aria-label="Action"
            placeholder="All actions"
            allowEmpty
            options={AUDIT_ACTIONS.map((a) => ({ value: a.value, label: a.label }))}
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>
        <div className="w-52">
          <Select
            aria-label="Actor"
            placeholder="Anyone"
            allowEmpty
            options={(members.data ?? []).map((m) => ({ value: m.userId, label: m.displayName }))}
            value={actorId}
            onChange={(e) => setActorId(e.target.value)}
          />
        </div>
        <label className="text-xs font-medium text-muted-foreground">
          From
          <input
            type="datetime-local"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="mt-1 block h-10 rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
          />
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          To
          <input
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="mt-1 block h-10 rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
          />
        </label>
        {action || actorId || from || to ? (
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={13} aria-hidden />}
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

      {logs.isLoading ? <Skeleton count={5} height={44} /> : null}
      {logs.isError ? <ErrorNote error={logs.error} onRetry={() => void logs.refetch()} /> : null}
      {logs.data && rows.length === 0 ? (
        <EmptyState title="No entries" description="Nothing matches these filters." />
      ) : null}

      {rows.length > 0 ? (
        <>
          <ul className="space-y-2.5 md:hidden" aria-label="Audit entries">
            {rows.map((e) => (
              <li key={e.id} className="rounded-2xl border border-border bg-card p-4 text-sm shadow-[var(--shadow-sm)]">
                <div className="font-semibold text-foreground">{auditActionLabel(e.action)}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {e.actorId ? (names.get(e.actorId) ?? 'Former member') : 'System'} · {new Date(e.createdAt).toLocaleString()}
                  {e.targetType ? ` · ${e.targetType.toLowerCase()}` : ''}
                </div>
                <div className="mt-1.5 font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">
                  {summarizeDetails(e.details)}
                </div>
              </li>
            ))}
          </ul>
          <div className="hidden overflow-x-auto rounded-2xl border border-border bg-card shadow-[var(--shadow-sm)] md:block">
            <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
              <thead className="border-b border-border bg-muted/60 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">When</th>
                  <th scope="col" className="px-4 py-3">Actor</th>
                  <th scope="col" className="px-4 py-3">Action</th>
                  <th scope="col" className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/70">
                {rows.map((e) => (
                  <tr key={e.id} className="align-top transition-colors hover:bg-muted/35">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted-foreground">
                      {new Date(e.createdAt).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-medium text-foreground">
                      {e.actorId ? (names.get(e.actorId) ?? 'Former member') : 'System'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground">{auditActionLabel(e.action)}</div>
                      {e.targetType ? <div className="text-xs text-muted-foreground">{e.targetType.toLowerCase()}</div> : null}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">
                      {summarizeDetails(e.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {logs.hasNextPage ? (
        <div className="flex justify-center">
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
