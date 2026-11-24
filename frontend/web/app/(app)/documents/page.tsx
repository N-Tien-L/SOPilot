'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, Download, FileCode2, FileText, FolderKanban, HardDrive, Loader2, Pencil, Search, Sparkles, Upload } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { TabList } from '@/components/app/TabList';
import { CategoriesPanel } from '@/components/documents/CategoriesPanel';
import { MetadataDialog } from '@/components/documents/MetadataDialog';
import { CountUp, ShinyText } from '@/components/effects';
import { FadeIn } from '@/components/motion/Primitives';
import { Badge, Button, EmptyState, Select, Skeleton, StatCard } from '@/components/ui';
import { getDownloadUrl } from '@/lib/api/endpoints';
import { classifyProcessingFailure } from '@/lib/upload/failure';
import type { DocumentStatus, DocumentView } from '@/lib/api/types';
import { documentStatusLabel, formatBytes, splitBytes } from '@/lib/chat/labels';
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
  const readyCount = rows.filter((d) => d.status === 'READY').length;
  const processingCount = rows.filter((d) => d.status === 'UPLOADED' || d.status === 'PROCESSING').length;
  const totalBytes = rows.reduce((sum, d) => sum + (d.currentVersion?.sizeBytes ?? 0), 0);
  const totalSize = splitBytes(totalBytes);
  const processing = processingCount > 0;
  const filtered = Boolean(status || categoryId || department || q);

  const departmentOptions = [
    { value: WHOLE_WORKSPACE, label: 'Whole workspace' },
    ...(publishers.data?.departments ?? []).map((d) => ({ value: d.departmentId, label: d.name })),
  ];

  return (
    <FadeIn className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {processing ? (
            <span className="inline-flex items-center gap-1.5 text-info-foreground">
              <Loader2 size={14} className="animate-spin" aria-hidden />
              <ShinyText active>Some documents are still processing; this list refreshes automatically.</ShinyText>
            </span>
          ) : manage ? (
            ownerDepartmentId
              ? 'Documents of your department, which you publish and manage.'
              : 'Documents you manage.'
          ) : (
            'Documents you can read in this workspace.'
          )}
        </p>
        {canUpload ? (
          <Button variant="primary" icon={<Upload size={15} aria-hidden />} onClick={() => setUploadOpen(true)}>
            Upload
          </Button>
        ) : null}
      </div>

      {/* Summary Counters */}
      {!docs.isLoading && !docs.isError ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label={filtered ? 'Matching documents' : 'Documents'}
            value={<CountUp to={rows.length} suffix={docs.hasNextPage ? '+' : ''} />}
            hint={filtered ? 'Filtered view' : 'Available in this view'}
            icon={<FileText size={14} aria-hidden />}
          />
          <StatCard
            label="Ready"
            value={<CountUp to={readyCount} />}
            hint="Indexed & searchable"
            icon={<CheckCircle2 size={14} aria-hidden />}
          />
          <StatCard
            label="Total size"
            value={<CountUp to={totalSize.value} decimals={totalSize.decimals} suffix={totalSize.unit} />}
            hint={docs.hasNextPage ? 'Loaded documents' : 'Original files combined'}
            icon={<HardDrive size={14} aria-hidden />}
          />
          {processingCount > 0 ? (
            <StatCard
              label="Processing"
              value={<CountUp to={processingCount} />}
              hint="Auto-refreshing every 5s"
              icon={<Loader2 size={14} className="animate-spin" aria-hidden />}
            />
          ) : (
            <StatCard
              label="Categories"
              value={<CountUp to={categories.data?.length ?? 0} />}
              hint="Active document groups"
              icon={<FolderKanban size={14} aria-hidden />}
            />
          )}
        </div>
      ) : null}

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card p-3 shadow-[var(--shadow-sm)]">
        <div className="relative min-w-[200px] flex-1">
          <Search size={14} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            aria-label="Search title"
            placeholder="Search title"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-10 w-full rounded-xl border border-input bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-placeholder outline-none transition-all focus:border-primary focus:ring-2 focus:ring-ring/20"
          />
        </div>
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
      </div>

      {docs.isLoading ? <Skeleton count={4} height={48} /> : null}
      {docs.isError ? <ErrorNote error={docs.error} onRetry={() => void docs.refetch()} /> : null}
      {docs.data && rows.length === 0 ? (
        <EmptyState
          title="No documents"
          description={filtered ? 'No document matches these filters.' : 'Nothing has been uploaded here yet.'}
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="relative overflow-x-auto rounded-2xl border border-border bg-card shadow-[var(--shadow-sm)]">
          <table className="w-full min-w-[48rem] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/60 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-3">Title</th>
                <th scope="col" className="px-3 py-3">Type</th>
                <th scope="col" className="px-3 py-3">Category</th>
                <th scope="col" className="px-3 py-3">Prepared by</th>
                <th scope="col" className="px-3 py-3">Visibility</th>
                <th scope="col" className="px-3 py-3">Status</th>
                <th scope="col" className="px-3 py-3">Ver</th>
                <th scope="col" className="px-3 py-3">Published by</th>
                <th scope="col" className="px-3 py-3 text-right"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {rows.map((d) => {
                const s = documentStatusLabel(d.status);
                const isMd = d.currentVersion?.fileType?.toUpperCase() === 'MD';
                return (
                  <tr key={d.id} className="group align-top transition-colors hover:bg-muted/35">
                    <td className="px-4 py-3.5">
                      <div className="flex items-start gap-2.5">
                        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/60 text-primary-strong">
                          {isMd ? <FileCode2 size={15} aria-hidden /> : <FileText size={15} aria-hidden />}
                        </span>
                        <div className="min-w-0">
                          {d.currentVersion ? (
                            <Link
                              href={`/documents/${d.id}`}
                              className="font-semibold text-foreground underline-offset-2 transition-colors hover:text-primary-strong hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                            >
                              {d.title}
                            </Link>
                          ) : (
                            <div className="font-semibold text-foreground">{d.title}</div>
                          )}
                          {manage && hasOpenSuggestion(d) ? (
                            <div className="mt-1">
                              <Badge variant="info" icon={<Sparkles size={11} aria-hidden />}>
                                Suggestions to review
                              </Badge>
                            </div>
                          ) : null}
                          {d.status === 'FAILED' ? (
                            <div className="mt-1 text-xs text-danger-foreground">
                              {classifyProcessingFailure(d.latestVersion.failureCode).message}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="rounded-md border border-border bg-muted/60 px-2 py-0.5 font-mono text-xs font-semibold text-foreground">
                        {d.currentVersion?.fileType?.toUpperCase() ?? '-'}
                      </span>
                      {d.currentVersion ? (
                        <div className="mt-1 text-xs text-muted-foreground">{formatBytes(d.currentVersion.sizeBytes)}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3.5 text-foreground">{d.category?.name ?? '-'}</td>
                    <td className="px-4 py-3.5 text-foreground">{d.preparedBy ?? '-'}</td>
                    <td className="px-4 py-3.5 text-xs text-muted-foreground">{visibilityText(d)}</td>
                    <td className="px-4 py-3.5">
                      <Badge
                        variant={s.tone === 'danger' ? 'danger' : s.tone}
                        icon={
                          d.status === 'PROCESSING' || d.status === 'UPLOADED' ? (
                            <Loader2 size={11} className="animate-spin" aria-hidden />
                          ) : d.status === 'READY' ? (
                            <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
                          ) : undefined
                        }
                      >
                        {s.label}
                      </Badge>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-muted-foreground">
                      v{d.latestVersion.versionNo}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="text-foreground">{d.createdBy.displayName}</div>
                      <div className="text-xs text-muted-foreground">{new Date(d.createdAt).toLocaleDateString()}</div>
                    </td>
                    <td className="px-4 py-3.5">
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
        <div className="flex justify-center pt-1">
          <Button variant="outline" loading={docs.isFetchingNextPage} onClick={() => void docs.fetchNextPage()}>
            Load more
          </Button>
        </div>
      ) : null}
    </FadeIn>
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
      <h1 className="text-2xl font-bold tracking-tight text-foreground">Documents</h1>
      {tabs.length > 1 ? <TabList label="Documents" tabs={tabs} current={current} onSelect={setTab} /> : null}
      <div
        className="mt-5"
        role={tabs.length > 1 ? 'tabpanel' : undefined}
        id={`panel-${current}`}
        aria-labelledby={tabs.length > 1 ? `tab-${current}` : undefined}
      >
        {me.isLoading ? <Skeleton count={4} height={48} /> : null}
        {!me.isLoading && current === 'view' ? (
          <DocumentList key="view" mode="view" initialQ={initialQ} departmentFilter={false} />
        ) : null}
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
