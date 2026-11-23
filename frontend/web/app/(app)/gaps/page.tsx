'use client';

import { useState } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, EmptyState, Skeleton } from '@/components/ui';
import { resolveKnowledgeGap } from '@/lib/api/endpoints';
import type { KnowledgeGap } from '@/lib/api/types';
import { gapFlags } from '@/lib/chat/labels';
import { useInvalidate, useKnowledgeGaps } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';

const PAGE_SIZE = 25;

function ResolveCell({ gap }: { gap: KnowledgeGap }) {
  const invalidate = useInvalidate();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function resolve() {
    setBusy(true);
    setError(null);
    try {
      await resolveKnowledgeGap(gap.messageId, note.trim() || undefined);
      await invalidate('gaps');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        Resolve
      </Button>
    );
  }
  return (
    <div className="space-y-2">
      <input
        aria-label="Resolution note (optional)"
        placeholder="Optional note"
        maxLength={500}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        className="w-full rounded-md border border-input bg-card px-2 py-1 text-sm"
      />
      <div className="flex gap-2">
        <Button size="sm" loading={busy} onClick={() => void resolve()}>
          Mark resolved
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
      {error ? <ErrorNote error={error} /> : null}
    </div>
  );
}

export default function GapsPage() {
  const role = useSessionStore((s) => s.workspace?.role);
  const [tab, setTab] = useState<'open' | 'resolved'>('open');
  const allowed = role === 'OWNER' || role === 'ADMIN';
  const gaps = useKnowledgeGaps(tab, PAGE_SIZE, allowed);

  if (!allowed) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners and admins only" description="Knowledge gaps are visible to workspace owners and admins." />
      </div>
    );
  }

  const rows = gaps.data?.pages.flat() ?? [];
  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-semibold">Knowledge gaps</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Questions the system could not answer, or that people marked as not helpful. Questions are masked for personal data and
        show no asker. To fill a gap, ask the document publisher to add or update a document.
      </p>
      <div role="tablist" aria-label="Gap status" className="mt-4 flex gap-1 border-b border-border">
        {(['open', 'resolved'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab === t ? 'border-b-2 border-primary font-semibold text-primary-strong' : 'text-muted-foreground'}`}
          >
            {t === 'open' ? 'Open' : 'Resolved'}
          </button>
        ))}
      </div>

      {gaps.isLoading ? <div className="mt-4"><Skeleton count={4} height={48} /></div> : null}
      {gaps.isError ? <ErrorNote error={gaps.error} className="mt-4" onRetry={() => void gaps.refetch()} /> : null}
      {gaps.data && rows.length === 0 ? (
        <div className="mt-6">
          <EmptyState title={tab === 'open' ? 'No open gaps' : 'No resolved gaps'} description="Nothing to review here." />
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">Question</th>
                <th scope="col" className="px-3 py-2">Flagged as</th>
                <th scope="col" className="px-3 py-2">{tab === 'open' ? 'Action' : 'Resolution'}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.messageId} className="border-t border-border align-top">
                  <td className="px-3 py-2">
                    <div>{g.question ?? 'Question not available'}</div>
                    <div className="text-xs text-muted-foreground">Asked {new Date(g.askedAt).toLocaleDateString()}</div>
                    {g.comments.filter((c) => c.comment).map((c, i) => (
                      <div key={i} className="mt-1 text-xs text-muted-foreground">
                        {c.vote < 0 ? 'Not helpful' : 'Helpful'}: {c.comment}
                      </div>
                    ))}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {gapFlags(g).map((f) => (
                        <Badge key={f} variant="neutral">{f}</Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {tab === 'open' ? (
                      <ResolveCell gap={g} />
                    ) : (
                      <div className="text-xs text-muted-foreground">
                        {g.resolvedAt ? `Resolved ${new Date(g.resolvedAt).toLocaleDateString()}` : 'Resolved'}
                        {g.resolutionNote ? <div className="text-sm text-foreground">{g.resolutionNote}</div> : null}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {gaps.hasNextPage ? (
        <div className="mt-4">
          <Button variant="outline" loading={gaps.isFetchingNextPage} onClick={() => void gaps.fetchNextPage()}>
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}
