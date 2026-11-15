'use client';

import { useState } from 'react';
import { Download } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, EmptyState, Select, Skeleton } from '@/components/ui';
import { getDownloadUrl } from '@/lib/api/endpoints';
import type { DocumentStatus, DocumentView } from '@/lib/api/types';
import { documentStatusLabel, formatBytes } from '@/lib/chat/labels';
import { useCategories, useDocuments } from '@/lib/query/hooks';

const STATUS_OPTIONS = [
  { value: 'READY', label: 'Ready' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'UPLOADED', label: 'Queued' },
  { value: 'FAILED', label: 'Failed' },
];

function visibilityText(d: DocumentView): string {
  if (d.visibility === 'WORKSPACE') return 'Workspace';
  const names = (d.departments ?? []).map((x) => x.name).filter(Boolean);
  return names.length > 0 ? `Departments: ${names.join(', ')}` : 'Departments';
}

function DownloadButton({ id }: { id: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      const { url } = await getDownloadUrl(id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button size="sm" variant="ghost" loading={busy} icon={<Download size={14} aria-hidden />} onClick={() => void download()}>
        Download
      </Button>
      {error ? <ErrorNote error={error} /> : null}
    </>
  );
}

export default function DocumentsPage() {
  const [status, setStatus] = useState<DocumentStatus | ''>('');
  const [categoryId, setCategoryId] = useState('');
  const [tag, setTag] = useState('');
  const categories = useCategories();
  const docs = useDocuments({
    ...(status ? { status } : {}),
    ...(categoryId ? { categoryId } : {}),
    ...(tag.trim() ? { tag: tag.trim() } : {}),
  });
  const rows = docs.data?.pages.flatMap((p) => p.data) ?? [];
  const processing = rows.some((d) => d.status === 'UPLOADED' || d.status === 'PROCESSING');

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Documents</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {processing ? 'Some documents are still processing; this list refreshes automatically.' : 'Documents you can read in this workspace.'}
          </p>
        </div>
        <Button variant="outline" disabled title="Uploading arrives with ticket V2-31">
          Upload
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <div className="w-40">
          <Select
            aria-label="Status"
            placeholder="All statuses"
            options={STATUS_OPTIONS}
            value={status}
            onChange={(e) => setStatus(e.target.value as DocumentStatus | '')}
          />
        </div>
        <div className="w-48">
          <Select
            aria-label="Category"
            placeholder="All categories"
            options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.name }))}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          />
        </div>
        <input
          aria-label="Tag"
          placeholder="Tag"
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          className="h-10 w-40 rounded-md border border-input bg-card px-3 text-sm"
        />
      </div>

      {docs.isLoading ? <div className="mt-4"><Skeleton count={4} height={44} /></div> : null}
      {docs.isError ? <ErrorNote error={docs.error} className="mt-4" /> : null}
      {docs.data && rows.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="No documents" description={status || categoryId || tag ? 'No document matches these filters.' : 'Nothing has been uploaded to this workspace yet.'} />
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[56rem] border-collapse text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">Title</th>
                <th scope="col" className="px-3 py-2">Type</th>
                <th scope="col" className="px-3 py-2">Category</th>
                <th scope="col" className="px-3 py-2">Visibility</th>
                <th scope="col" className="px-3 py-2">Status</th>
                <th scope="col" className="px-3 py-2">Ver</th>
                <th scope="col" className="px-3 py-2">Uploaded by</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => {
                const s = documentStatusLabel(d.status);
                return (
                  <tr key={d.id} className="border-t border-border align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{d.title}</div>
                      {d.tags.length > 0 ? <div className="text-xs text-muted-foreground">{d.tags.join(', ')}</div> : null}
                      {d.status === 'FAILED' && d.latestVersion.failureMessage ? (
                        <div className="text-xs text-danger-foreground">{d.latestVersion.failureMessage}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{d.currentVersion?.fileType?.toUpperCase() ?? '-'}
                      {d.currentVersion ? <div className="text-xs text-muted-foreground">{formatBytes(d.currentVersion.sizeBytes)}</div> : null}
                    </td>
                    <td className="px-3 py-2">{d.category?.name ?? '-'}</td>
                    <td className="px-3 py-2">{visibilityText(d)}</td>
                    <td className="px-3 py-2">
                      <Badge variant={s.tone === 'danger' ? 'danger' : s.tone}>{s.label}</Badge>
                    </td>
                    <td className="px-3 py-2">v{d.latestVersion.versionNo}</td>
                    <td className="px-3 py-2">
                      {d.createdBy.displayName}
                      <div className="text-xs text-muted-foreground">{new Date(d.createdAt).toLocaleDateString()}</div>
                    </td>
                    <td className="px-3 py-2">{d.currentVersion ? <DownloadButton id={d.id} /> : null}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {docs.hasNextPage ? (
        <div className="mt-4">
          <Button variant="outline" loading={docs.isFetchingNextPage} onClick={() => void docs.fetchNextPage()}>
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}
