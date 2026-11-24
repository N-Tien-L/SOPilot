'use client';

import { useState } from 'react';
import { Check } from 'lucide-react';
import { toast } from 'sonner';
import { ErrorNote } from '@/components/app/ErrorNote';
import { TabList } from '@/components/app/TabList';
import { FadeIn } from '@/components/motion/Primitives';
import { Badge, Button, EmptyState, PageHeader, Skeleton } from '@/components/ui';
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
      toast.success('Knowledge gap marked as resolved');
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
        className="h-9 w-full rounded-xl border border-input bg-background px-3 text-xs text-foreground placeholder:text-placeholder outline-none focus:border-primary focus:ring-2 focus:ring-ring/20"
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
        <EmptyState
          title="Owners and admins only"
          description="Knowledge gaps are visible to workspace owners and admins."
        />
      </div>
    );
  }

  const rows = gaps.data?.pages.flat() ?? [];
  return (
    <div className="mx-auto max-w-5xl p-6">
      <FadeIn>
        <PageHeader
          title="Knowledge gaps"
          description="Questions the system could not answer, or that people marked as not helpful. Questions are masked for personal data and show no asker. To fill a gap, ask the document publisher to add or update a document."
        />
      </FadeIn>

      <TabList
        label="Gap status"
        tabs={[
          { id: 'open', label: 'Open' },
          { id: 'resolved', label: 'Resolved' },
        ]}
        current={tab}
        onSelect={setTab}
      />

      <div className="mt-5" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {gaps.isLoading ? <Skeleton count={4} height={52} /> : null}
        {gaps.isError ? <ErrorNote error={gaps.error} onRetry={() => void gaps.refetch()} /> : null}
        {gaps.data && rows.length === 0 ? (
          <EmptyState
            title={tab === 'open' ? 'No open gaps' : 'No resolved gaps'}
            description="Nothing to review here."
          />
        ) : null}

        {rows.length > 0 ? (
          <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-[var(--shadow-sm)]">
            <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
              <thead className="border-b border-border bg-muted/60 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">Question</th>
                  <th scope="col" className="px-4 py-3">Flagged as</th>
                  <th scope="col" className="px-4 py-3">{tab === 'open' ? 'Action' : 'Resolution'}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/70">
                {rows.map((g) => (
                  <tr key={g.messageId} className="align-top transition-colors hover:bg-muted/35">
                    <td className="px-4 py-3.5">
                      <div className="font-medium text-foreground">{g.question ?? 'Question not available'}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        Asked {new Date(g.askedAt).toLocaleDateString()}
                      </div>
                      {g.comments
                        .filter((c) => c.comment)
                        .map((c, i) => (
                          <div key={i} className="mt-1.5 rounded-lg bg-muted/50 px-2.5 py-1.5 text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground">
                              {c.vote < 0 ? 'Not helpful' : 'Helpful'}:
                            </span>{' '}
                            {c.comment}
                          </div>
                        ))}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-wrap gap-1.5">
                        {gapFlags(g).map((f) => (
                          <Badge key={f} variant="warning">
                            {f}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      {tab === 'open' ? (
                        <ResolveCell gap={g} />
                      ) : (
                        <div className="space-y-1 text-xs text-muted-foreground">
                          <Badge variant="success" icon={<Check size={11} aria-hidden />}>
                            {g.resolvedAt ? `Resolved ${new Date(g.resolvedAt).toLocaleDateString()}` : 'Resolved'}
                          </Badge>
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
          <div className="mt-4 flex justify-center">
            <Button variant="outline" loading={gaps.isFetchingNextPage} onClick={() => void gaps.fetchNextPage()}>
              Load more
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
