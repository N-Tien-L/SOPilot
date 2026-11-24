'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Pencil } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { MetadataDialog } from '@/components/documents/MetadataDialog';
import { FadeIn } from '@/components/motion/Primitives';
import { Badge, Button, Skeleton, Tabs } from '@/components/ui';
import { ContentViewer, NotAvailable } from '@/components/viewer/ContentViewer';
import { ProcessingReport } from '@/components/viewer/ProcessingReport';
import { ApiError } from '@/lib/api/errors';
import { canEditDetails } from '@/lib/admin/metadata';
import { documentStatusLabel } from '@/lib/chat/labels';
import { useDocument, useMyMember } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { versionNotice } from '@/lib/viewer/labels';

// FR-31: "Content recognized by the system". It opens only when the document has a current
// version (READY); a document outside the caller's access, or without content yet, shows nothing.

function DocumentContentPage({ id }: { id: string }) {
  const doc = useDocument(id);
  const d = doc.data;
  const [editing, setEditing] = useState(false);
  const me = useMyMember();
  const role = useSessionStore((s) => s.workspace?.role);

  let body: React.ReactNode;
  if (doc.isLoading) body = <Skeleton count={4} height={36} />;
  else if (doc.isError)
    body = doc.error instanceof ApiError && doc.error.status === 404 ? <NotAvailable /> : <ErrorNote error={doc.error} />;
  else if (d && !d.currentVersion)
    body = (
      <p role="note" className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-[var(--shadow-sm)]">
        This document has no recognized content yet ({documentStatusLabel(d.latestVersion.status).label.toLowerCase()}). It opens here once processing has finished.
      </p>
    );
  else if (d?.currentVersion)
    body = (
      <Tabs
        variant="underline"
        tabs={[
          {
            value: 'content',
            label: 'Recognized content',
            content: (
              <ContentViewer
                documentId={d.id}
                versionId={d.currentVersion.id}
                originalName={d.currentVersion.originalName}
                notice={versionNotice(d)}
              />
            ),
          },
          {
            value: 'report',
            label: 'Processing report',
            content: <ProcessingReport documentId={d.id} versionId={d.currentVersion.id} />,
          },
        ]}
      />
    );

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-6">
      <FadeIn>
        <Link
          href="/documents"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary-strong underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          <ArrowLeft size={13} aria-hidden /> Documents
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-tight text-foreground [overflow-wrap:anywhere]">
                {d ? d.title : 'Content recognized by the system'}
              </h1>
              {d?.currentVersion ? (
                <Badge variant="success">v{d.currentVersion.versionNo} · Ready</Badge>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Content recognized by the system
              {d?.currentVersion ? ` · version ${d.currentVersion.versionNo}` : ''}
              {d?.preparedBy ? ` · Prepared by ${d.preparedBy}` : ''}
            </p>
          </div>
          {d && canEditDetails(me.data?.publisherOf, role, d) ? (
            <Button size="sm" variant="outline" icon={<Pencil size={14} aria-hidden />} onClick={() => setEditing(true)}>
              Edit details
            </Button>
          ) : null}
        </div>
      </FadeIn>

      {d && editing ? <MetadataDialog doc={d} onClose={() => setEditing(false)} /> : null}
      {body}
    </div>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <DocumentContentPage id={id} />;
}
