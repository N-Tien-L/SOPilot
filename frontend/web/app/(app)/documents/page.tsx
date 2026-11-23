'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Download, Pencil, Upload } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { TabList } from '@/components/app/TabList';
import { CategoriesPanel } from '@/components/documents/CategoriesPanel';
import { MetadataDialog } from '@/components/documents/MetadataDialog';
import { Badge, Button, EmptyState, Select, Skeleton } from '@/components/ui';
import { getDownloadUrl } from '@/lib/api/endpoints';
import { classifyProcessingFailure } from '@/lib/upload/failure';
import type { DocumentStatus, DocumentView } from '@/lib/api/types';
import { documentStatusLabel, formatBytes } from '@/lib/chat/labels';
import { canEditDetails, hasOpenSuggestion } from '@/lib/admin/metadata';
import { documentsLayout, documentsTabs, uploadScopes, type DocumentsTab } from '@/lib/admin/documentsLayout';
import { useCategories, useDocuments, useMyMember, usePublishers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { useUploadStore } from '@/store/upload-store';

const STATUS_OPTIONS = [
  { value: 'READY', label: 'Ready' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'UPLOADED', label: 'Queued' },
  { value: 'FAILED', label: 'Failed' },
];

const WHOLE_WORKSPACE = '__workspace__';

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

/**
 * One list of documents. `view` is read-only. `manage` adds Upload and Edit, and is what a publisher
 * works in: `ownerDepartmentId` pins it to one department's documents; `departmentFilter` lets an
 * owner or admin narrow all documents by owning department (the server allows that filter only to them).
 */
function DocumentList({
  mode,
  initialQ,
  ownerDepartmentId,
  departmentFilter,
}: {
  mode: 'view' | 'manage';
  initialQ: string;
  ownerDepartmentId?: string;
  departmentFilter: boolean;
}) {
  const [status, setStatus] = useState<DocumentStatus | ''>('');
  const [categoryId, setCategoryId] = useState('');
  const [department, setDepartment] = useState('');
  const [q, setQ] = useState(initialQ);
  const [editing, setEditing] = useState<DocumentView | null>(null);
  const setUploadOpen = useUploadStore((s) => s.setDialogOpen);
  const me = useMyMember();
  const role = useSessionStore((s) => s.workspace?.role);
  const publishers = usePublishers();
  const manage = mode === 'manage';
  const canUpload = manage && uploadScopes(me.data?.publisherOf).length > 0;
  const categories = useCategories();
  const pinned = ownerDepartmentId ?? (department && department !== WHOLE_WORKSPACE ? department : undefined);
  const docs = useDocuments({
    ...(status ? { status } : {}),
    ...(categoryId ? { categoryId } : {}),
    ...(q.trim() ? { q: q.trim() } : {}),
    ...(pinned ? { ownerDepartmentId: pinned } : {}),
    ...(department === WHOLE_WORKSPACE ? { visibility: 'WORKSPACE' as const } : {}),
  });
  const rows = docs.data?.pages.flatMap((p) => p.data) ?? [];
  const processing = rows.some((d) => d.status === 'UPLOADED' || d.status === 'PROCESSING');
  const filtered = Boolean(status || categoryId || department || q);

  const departmentOptions = [
    { value: WHOLE_WORKSPACE, label: 'Whole workspace' },
    ...(publishers.data?.departments ?? []).map((d) => ({ value: d.departmentId, label: d.name })),
  ];

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {processing
            ? 'Some documents are still processing; this list refreshes automatically.'
            : manage
              ? ownerDepartmentId
                ? 'Documents of your department, which you publish and manage.'
                : 'Documents you manage.'
              : 'Documents you can read in this workspace.'}
        </p>
        {canUpload ? (
          <Button variant="primary" icon={<Upload size={16} aria-hidden />} onClick={() => setUploadOpen(true)}>
            Upload
          </Button>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <div className="w-40">
          <Select
            aria-label="Status"
            placeholder="All statuses"
            allowEmpty
            options={STATUS_OPTIONS}
            value={status}
            onChange={(e) => setStatus(e.target.value as DocumentStatus | '')}
          />
        </div>
        <div className="w-48">
          <Select
            aria-label="Category"
            placeholder="All categories"
            allowEmpty
            options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.name }))}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          />
        </div>
        {departmentFilter ? (
          <div className="w-52">
            <Select
              aria-label="Department"
              placeholder="All departments"
              allowEmpty
              options={departmentOptions}
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            />
          </div>
        ) : null}
        <input
          aria-label="Search title"
          placeholder="Search title"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="h-10 w-48 rounded-md border border-input bg-card px-3 text-sm"
        />
      </div>

      {docs.isLoading ? <div className="mt-4"><Skeleton count={4} height={44} /></div> : null}
      {docs.isError ? <ErrorNote error={docs.error} className="mt-4" /> : null}
      {docs.data && rows.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No documents"
            description={filtered ? 'No document matches these filters.' : 'Nothing has been uploaded here yet.'}
          />
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="relative mt-4 overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[62rem] border-collapse text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2">Title</th>
                <th scope="col" className="px-3 py-2">Type</th>
                <th scope="col" className="px-3 py-2">Category</th>
                <th scope="col" className="px-3 py-2">Prepared by</th>
                <th scope="col" className="px-3 py-2">Visibility</th>
                <th scope="col" className="px-3 py-2">Status</th>
                <th scope="col" className="px-3 py-2">Ver</th>
                <th scope="col" className="px-3 py-2">Published by</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => {
                const s = documentStatusLabel(d.status);
                return (
                  <tr key={d.id} className="border-t border-border align-top">
                    <td className="px-3 py-2">
                      {d.currentVersion ? (
                        <Link href={`/documents/${d.id}`} className="font-medium text-primary-strong underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-ring">
                          {d.title}
                        </Link>
                      ) : (
                        <div className="font-medium">{d.title}</div>
                      )}
                      {manage && hasOpenSuggestion(d) ? <div className="mt-1"><Badge variant="info">Suggestions to review</Badge></div> : null}
                      {d.status === 'FAILED' ? (
                        <div className="text-xs text-danger-foreground">{classifyProcessingFailure(d.latestVersion.failureCode).message}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{d.currentVersion?.fileType?.toUpperCase() ?? '-'}
                      {d.currentVersion ? <div className="text-xs text-muted-foreground">{formatBytes(d.currentVersion.sizeBytes)}</div> : null}
                    </td>
                    <td className="px-3 py-2">{d.category?.name ?? '-'}</td>
                    <td className="px-3 py-2">{d.preparedBy ?? '-'}</td>
                    <td className="px-3 py-2">{visibilityText(d)}</td>
                    <td className="px-3 py-2">
                      <Badge variant={s.tone === 'danger' ? 'danger' : s.tone}>{s.label}</Badge>
                    </td>
                    <td className="px-3 py-2">v{d.latestVersion.versionNo}</td>
                    <td className="px-3 py-2">
                      {d.createdBy.displayName}
                      <div className="text-xs text-muted-foreground">{new Date(d.createdAt).toLocaleDateString()}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap justify-end gap-1">
                        {manage && canEditDetails(me.data?.publisherOf, role, d) ? (
                          <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden />} onClick={() => setEditing(d)}>
                            Edit
                          </Button>
                        ) : null}
                        {d.currentVersion ? <DownloadButton id={d.id} /> : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {editing ? <MetadataDialog key={editing.id} doc={editing} onClose={() => setEditing(null)} /> : null}
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

const TAB_LABEL: Record<DocumentsTab, string> = { view: 'All documents', manage: 'Manage', categories: 'Categories' };

function DocumentsView({ initialQ }: { initialQ: string }) {
  const me = useMyMember();
  const role = useSessionStore((s) => s.workspace?.role);
  const publishers = usePublishers();
  const isManager = role === 'OWNER' || role === 'ADMIN';
  const layout = documentsLayout(me.data?.publisherOf, role);
  const tabIds = documentsTabs(layout, isManager);
  const [tab, setTab] = useState<DocumentsTab | null>(null);
  const current = tab && tabIds.includes(tab) ? tab : tabIds[0];

  const departmentName = layout.manageDepartmentId
    ? publishers.data?.departments.find((d) => d.departmentId === layout.manageDepartmentId)?.name
    : undefined;
  const tabs = tabIds.map((id) => ({
    id,
    label:
      id === 'manage' && layout.manageDepartmentId
        ? `Manage${departmentName ? `: ${departmentName}` : ''}`
        : id === 'view' && !tabIds.includes('manage')
          ? 'Documents'
          : TAB_LABEL[id],
  }));

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Documents</h1>
      {tabs.length > 1 ? <TabList label="Documents" tabs={tabs} current={current} onSelect={setTab} /> : null}
      <div className="mt-4" role={tabs.length > 1 ? 'tabpanel' : undefined} id={`panel-${current}`} aria-labelledby={tabs.length > 1 ? `tab-${current}` : undefined}>
        {me.isLoading ? <Skeleton count={4} height={44} /> : null}
        {!me.isLoading && current === 'view' ? <DocumentList key="view" mode="view" initialQ={initialQ} departmentFilter={false} /> : null}
        {!me.isLoading && current === 'manage' ? (
          <DocumentList
            key={`manage:${layout.manageDepartmentId ?? 'all'}`}
            mode="manage"
            initialQ={initialQ}
            ownerDepartmentId={layout.manageDepartmentId ?? undefined}
            departmentFilter={layout.manageAll && isManager}
          />
        ) : null}
        {current === 'categories' ? <CategoriesPanel /> : null}
      </div>
    </div>
  );
}

/**
 * The upload dialog links a duplicate here with `?q=<title>`. The view is keyed by that value, so
 * following the link while already on this page re-applies the filter.
 */
export default function DocumentsPage() {
  return (
    <Suspense fallback={null}>
      <DocumentsRoute />
    </Suspense>
  );
}

function DocumentsRoute() {
  const initialQ = useSearchParams().get('q') ?? '';
  return <DocumentsView key={initialQ} initialQ={initialQ} />;
}
