'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowRight, FileCode2, FileText, Loader2, RefreshCw, Search, UploadCloud, X } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, Skeleton } from '@/components/ui';
import type { PublisherOf } from '@/lib/admin/documentsLayout';
import { canWriteDocument } from '@/lib/admin/metadata';
import type { DocumentView } from '@/lib/api/types';
import { documentStatusLabel, formatBytes } from '@/lib/chat/labels';
import { useDocuments } from '@/lib/query/hooks';
import { selectVersionFile } from '@/lib/upload/controller';
import { activeDocumentIds } from '@/lib/upload/queue';
import { checkFile } from '@/lib/upload/validate';
import { useUploadStore } from '@/store/upload-store';

const ACCEPT = '.pdf,.md,.markdown,application/pdf,text/markdown';

interface VersionUploadPanelProps {
  publisherOf: PublisherOf | undefined;
  full: boolean;
}

function scopeBadgeLabel(doc: DocumentView): string {
  if (doc.visibility === 'WORKSPACE') return 'Workspace';
  return doc.ownerDepartment?.name ?? 'Department';
}

/**
 * Two-step flow inside UploadDialog for uploading a new version of an existing document:
 * 1. Search and pick an existing document the publisher is allowed to write to.
 * 2. Pick a single replacement file and confirm with an explicit "Upload v{next}" click.
 */
export function VersionUploadPanel({ publisherOf, full }: VersionUploadPanelProps) {
  const queue = useUploadStore((s) => s.queue);
  const target = useUploadStore((s) => s.targetDocument);
  const setTarget = useUploadStore((s) => s.setTargetDocument);

  const [rawQuery, setRawQuery] = useState('');
  const [query, setQuery] = useState('');
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [stagedError, setStagedError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(rawQuery.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  const workspaceOnly = Boolean(publisherOf?.workspace) && !publisherOf?.departmentId;
  const deptOnly = !publisherOf?.workspace && Boolean(publisherOf?.departmentId);

  const docs = useDocuments({
    ...(query ? { q: query } : {}),
    ...(workspaceOnly ? { visibility: 'WORKSPACE' as const } : {}),
    ...(deptOnly && publisherOf?.departmentId ? { ownerDepartmentId: publisherOf.departmentId } : {}),
  });

  const activeIds = activeDocumentIds(queue);
  const allRows = docs.data?.pages.flatMap((p) => p.data) ?? [];
  const writableRows = allRows.filter((d) => canWriteDocument(publisherOf, d));

  function stageCandidate(file: File | undefined) {
    if (!file) return;
    const problem = checkFile({ name: file.name, size: file.size });
    if (problem) {
      setStagedFile(null);
      setStagedError(problem.message);
      return;
    }
    setStagedError(null);
    setStagedFile(file);
  }

  function handleConfirmUpload() {
    if (!target || !stagedFile) return;
    const ok = selectVersionFile(target, stagedFile);
    if (ok) {
      setStagedFile(null);
      setStagedError(null);
      setTarget(null);
    }
  }

  function handleChangeTarget() {
    setStagedFile(null);
    setStagedError(null);
    setTarget(null);
  }

  if (!target) {
    return (
      <div className="space-y-3">
        <div>
          <label htmlFor="version-doc-search" className="mb-1.5 block text-xs font-semibold text-foreground">
            1. Select the document to update
          </label>
          <div className="relative">
            <Search
              size={14}
              aria-hidden
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              id="version-doc-search"
              type="text"
              placeholder="Search documents by title..."
              value={rawQuery}
              onChange={(e) => setRawQuery(e.target.value)}
              className="h-10 w-full rounded-xl border border-input bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-placeholder outline-none transition-all focus:border-primary focus:ring-2 focus:ring-ring/20"
            />
          </div>
        </div>

        <div className="max-h-64 overflow-y-auto rounded-xl border border-border bg-muted/20">
          {docs.isLoading ? (
            <div className="p-3">
              <Skeleton count={3} height={44} />
            </div>
          ) : docs.isError ? (
            <div className="p-3">
              <ErrorNote error={docs.error} onRetry={() => void docs.refetch()} />
            </div>
          ) : writableRows.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              {query
                ? 'No matching documents you can publish to.'
                : 'No documents available to update yet. Upload a new document first.'}
            </p>
          ) : (
            <ul className="divide-y divide-border/70" aria-label="Documents available for new version">
              {writableRows.map((d) => {
                const isProcessing =
                  d.latestVersion.status === 'UPLOADED' ||
                  d.latestVersion.status === 'PROCESSING' ||
                  activeIds.has(d.id);
                const status = documentStatusLabel(d.latestVersion.status);
                const isMd = d.currentVersion?.fileType?.toUpperCase() === 'MD';
                const subtitle = [
                  d.currentVersion?.originalName,
                  d.category?.name,
                  scopeBadgeLabel(d),
                ]
                  .filter(Boolean)
                  .join(' · ');

                return (
                  <li key={d.id}>
                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => {
                        setStagedFile(null);
                        setStagedError(null);
                        setTarget({
                          documentId: d.id,
                          title: d.title,
                          currentVersionNo: d.latestVersion.versionNo,
                        });
                      }}
                      className="flex w-full items-start justify-between gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-55"
                    >
                      <div className="flex min-w-0 items-start gap-2.5">
                        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-primary-strong">
                          {isMd ? <FileCode2 size={14} aria-hidden /> : <FileText size={14} aria-hidden />}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">{d.title}</p>
                          <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
                        <span className="font-mono text-xs font-medium text-muted-foreground">
                          v{d.latestVersion.versionNo}
                        </span>
                        {isProcessing ? (
                          <Badge variant="info" icon={<Loader2 size={11} className="animate-spin" aria-hidden />}>
                            Processing
                          </Badge>
                        ) : (
                          <Badge variant={status.tone === 'danger' ? 'danger' : status.tone}>{status.label}</Badge>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {docs.hasNextPage ? (
          <div className="flex justify-center">
            <Button size="sm" variant="ghost" loading={docs.isFetchingNextPage} onClick={() => void docs.fetchNextPage()}>
              Load more documents
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  const nextVersionNo = target.currentVersionNo + 1;
  const targetBusy = activeIds.has(target.documentId);

  return (
    <div className="space-y-3.5">
      <div className="rounded-xl border border-border bg-muted/40 p-3.5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Updating document</p>
            <p className="mt-0.5 break-words text-sm font-semibold text-foreground">{target.title}</p>
            <div className="mt-1.5 inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-primary-strong">
              <span>v{target.currentVersionNo}</span>
              <ArrowRight size={12} aria-hidden />
              <span>v{nextVersionNo}</span>
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={handleChangeTarget}>
            Change
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Visibility, category, and metadata stay unchanged. The current version continues serving Q&amp;A until v
          {nextVersionNo} is ready.
        </p>
      </div>

      {targetBusy ? (
        <p role="status" className="rounded-xl border border-info/30 bg-info-soft p-3 text-xs font-medium text-info-foreground">
          A new version for this document is already uploading or processing in the queue below.
        </p>
      ) : null}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          stageCandidate(e.dataTransfer.files[0]);
        }}
        className={`flex flex-col items-center gap-2.5 rounded-2xl border-2 border-dashed text-center text-sm transition-all ${
          targetBusy || full ? 'pointer-events-none opacity-50 ' : ''
        }p-5 ${
          dragging
            ? 'border-primary bg-primary-soft/60 shadow-[0_0_0_4px_rgba(20,184,166,0.12)]'
            : 'border-border-strong bg-muted/40 hover:border-primary/50'
        }`}
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary-strong">
          <UploadCloud size={20} aria-hidden />
        </span>
        <p className="font-medium text-foreground">
          {stagedFile ? 'Drop another file to replace selection, or' : `Drop the v${nextVersionNo} file here, or`}
        </p>
        <Button variant="outline" size="sm" onClick={() => picker.current?.click()}>
          {stagedFile ? 'Choose a different file' : 'Choose file'}
        </Button>
        <input
          ref={picker}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-label={`New version file for ${target.title}`}
          onChange={(e) => {
            stageCandidate(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
        {full ? (
          <p className="text-xs text-muted-foreground">The batch is full. Clear finished files to add more.</p>
        ) : null}
      </div>

      {stagedError ? (
        <p role="alert" className="rounded-xl bg-danger-soft/70 px-3 py-2 text-xs font-medium text-danger-foreground">
          {stagedError}
        </p>
      ) : null}

      {stagedFile ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary-soft/30 p-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">
              <FileText size={15} aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">{stagedFile.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(stagedFile.size)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              icon={<X size={14} aria-hidden />}
              onClick={() => {
                setStagedFile(null);
                setStagedError(null);
              }}
            >
              Remove
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={full || targetBusy}
              icon={<RefreshCw size={14} aria-hidden />}
              onClick={handleConfirmUpload}
            >
              Upload v{nextVersionNo}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
