'use client';

import { useState, type FormEvent } from 'react';
import { Plus } from 'lucide-react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, ConfirmDialog, EmptyState, Input, Modal, Skeleton } from '@/components/ui';
import type { ArchiveStatus } from '@/lib/api/types';
import { useInvalidate } from '@/lib/query/hooks';
import { useAction } from './useAction';

export interface NamedItem {
  id: string;
  name: string;
  status?: ArchiveStatus;
}

export interface NamedListApi {
  create: (name: string) => Promise<unknown>;
  update: (id: string, patch: { name?: string; status?: ArchiveStatus }) => Promise<unknown>;
  remove: (id: string) => Promise<unknown>;
}

interface Props {
  /** "department" or "category", used in the copy. */
  noun: string;
  items: NamedItem[] | undefined;
  loading: boolean;
  error: unknown;
  api: NamedListApi;
  /** Query-key prefixes to refresh after a change. */
  invalidate: readonly string[];
  emptyHint: string;
  /** Departments also show in member forms; categories in the document form. */
  note?: string;
}

function NameDialog({
  title,
  initial,
  submitLabel,
  onSubmit,
  onClose,
}: {
  title: string;
  initial: string;
  submitLabel: string;
  onSubmit: (name: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const { run, busy, error } = useAction();
  const [name, setName] = useState(initial);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await run(() => onSubmit(name.trim()))) onClose();
  }
  return (
    <Modal open onClose={onClose} title={title} size="sm">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Name" required maxLength={100} autoFocus value={name} onChange={(e) => setName(e.target.value)} />
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={name.trim() === '' || name.trim() === initial}>
            {submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/**
 * A flat list (departments, categories): create, rename, archive/restore, delete when unused.
 * Delete is refused by the server while something still references the item; its fixed message
 * is shown in the dialog and archiving stays available.
 */
export function NamedListPanel({ noun, items, loading, error, api, invalidate, emptyHint, note }: Props) {
  const refresh = useInvalidate();
  const [dialog, setDialog] = useState<{ kind: 'create' } | { kind: 'rename'; item: NamedItem } | null>(null);
  const [deleting, setDeleting] = useState<NamedItem | null>(null);
  const action = useAction();

  async function after() {
    for (const key of invalidate) await refresh(key);
  }

  async function toggleArchive(item: NamedItem) {
    const next: ArchiveStatus = item.status === 'ARCHIVED' ? 'ACTIVE' : 'ARCHIVED';
    if (await action.run(() => api.update(item.id, { status: next }))) await after();
  }

  async function confirmDelete() {
    if (!deleting) return;
    if (await action.run(() => api.remove(deleting.id))) {
      await after();
      setDeleting(null);
    }
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{note}</p>
        <Button variant="primary" icon={<Plus size={16} aria-hidden />} onClick={() => setDialog({ kind: 'create' })}>
          New {noun}
        </Button>
      </div>
      {action.error && !deleting ? <ErrorNote error={action.error} className="mb-2" /> : null}
      {loading ? <Skeleton count={3} height={40} /> : null}
      {error ? <ErrorNote error={error} /> : null}
      {items && items.length === 0 ? <EmptyState title={`No ${noun}s yet`} description={emptyHint} /> : null}
      {items && items.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card text-sm">
          {items.map((item) => {
            const archived = item.status === 'ARCHIVED';
            return (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="flex items-center gap-2">
                  <span className={archived ? 'text-muted-foreground' : 'font-medium'}>{item.name}</span>
                  {archived ? <Badge variant="neutral">Archived</Badge> : null}
                </span>
                <span className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: 'rename', item })}>
                    Rename
                  </Button>
                  <Button size="sm" variant="ghost" disabled={action.busy} onClick={() => void toggleArchive(item)}>
                    {archived ? 'Restore' : 'Archive'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      action.reset();
                      setDeleting(item);
                    }}
                  >
                    Delete
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
      {dialog?.kind === 'create' ? (
        <NameDialog
          title={`New ${noun}`}
          initial=""
          submitLabel="Create"
          onSubmit={async (name) => {
            await api.create(name);
            await after();
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {dialog?.kind === 'rename' ? (
        <NameDialog
          title={`Rename ${noun}`}
          initial={dialog.item.name}
          submitLabel="Save"
          onSubmit={async (name) => {
            await api.update(dialog.item.id, { name });
            await after();
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          open
          onClose={() => setDeleting(null)}
          onConfirm={() => void confirmDelete()}
          title={`Delete ${noun}`}
          confirmLabel="Delete"
          variant="danger"
          loading={action.busy}
          message={
            <>
              Delete <strong>{deleting.name}</strong>? This works only while nothing uses it; otherwise archive it instead.
              {action.error ? <ErrorNote error={action.error} className="mt-2" /> : null}
            </>
          }
        />
      ) : null}
    </>
  );
}
