'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { Button, ConfirmDialog, Input, Modal } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import { deleteConversation, renameConversation } from '@/lib/api/endpoints';
import type { ConversationSummary } from '@/lib/api/types';
import { useConversations, useInvalidate } from '@/lib/query/hooks';

/** FR-15: the caller's own conversations (the API never returns another user's), with rename and delete. */
export function ConversationList() {
  const router = useRouter();
  const pathname = usePathname();
  const activeId = pathname.startsWith('/chat/') ? pathname.slice('/chat/'.length) : null;
  const { data, isLoading, isError, error } = useConversations();
  const invalidate = useInvalidate();
  const [renaming, setRenaming] = useState<ConversationSummary | null>(null);
  const [title, setTitle] = useState('');
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  async function submitRename(event: FormEvent) {
    event.preventDefault();
    if (!renaming) return;
    setBusy(true);
    setActionError(null);
    try {
      await renameConversation(renaming.id, title.trim());
      await invalidate('conversations');
      await invalidate('conversation', renaming.id);
      setRenaming(null);
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setActionError(null);
    try {
      await deleteConversation(deleting.id);
      await invalidate('conversations');
      if (deleting.id === activeId) router.push('/chat');
      setDeleting(null);
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-0">
      <div className="flex items-center justify-between px-3 pb-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-sidebar-muted">Conversations</span>
        <Link
          href="/chat"
          aria-label="New chat"
          className="rounded-md p-1 text-sidebar-muted hover:bg-white/10 hover:text-sidebar-foreground"
        >
          <Plus size={16} aria-hidden />
        </Link>
      </div>
      {isLoading ? <p className="px-3 py-1 text-xs text-sidebar-muted">Loading…</p> : null}
      {isError ? <ErrorNote error={error} className="px-3 py-1 !text-danger-soft" /> : null}
      {data && data.length === 0 ? <p className="px-3 py-1 text-xs text-sidebar-muted">No conversations yet.</p> : null}
      <ul>
        {(data ?? []).map((c) => (
          <li key={c.id} className="group relative">
            <Link
              href={`/chat/${c.id}`}
              aria-current={c.id === activeId ? 'page' : undefined}
              className={`block truncate rounded-md py-1.5 pl-3 pr-14 text-sm ${
                c.id === activeId ? 'bg-white/15 text-sidebar-foreground' : 'text-sidebar-muted hover:bg-white/10'
              }`}
            >
              {c.title || 'New conversation'}
            </Link>
            <span className="absolute inset-y-0 right-1 hidden items-center gap-0.5 group-focus-within:flex group-hover:flex">
              <button
                type="button"
                aria-label={`Rename ${c.title || 'conversation'}`}
                className="rounded p-1 text-sidebar-muted hover:bg-white/15 hover:text-sidebar-foreground"
                onClick={() => {
                  setActionError(null);
                  setTitle(c.title ?? '');
                  setRenaming(c);
                }}
              >
                <Pencil size={13} aria-hidden />
              </button>
              <button
                type="button"
                aria-label={`Delete ${c.title || 'conversation'}`}
                className="rounded p-1 text-sidebar-muted hover:bg-white/15 hover:text-sidebar-foreground"
                onClick={() => {
                  setActionError(null);
                  setDeleting(c);
                }}
              >
                <Trash2 size={13} aria-hidden />
              </button>
            </span>
          </li>
        ))}
      </ul>

      <Modal open={renaming !== null} onClose={() => setRenaming(null)} title="Rename conversation">
        <form onSubmit={submitRename} className="space-y-4">
          <Input label="Title" required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
          {actionError ? <ErrorNote error={actionError} /> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={busy} disabled={title.trim().length === 0}>
              Save
            </Button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete conversation?"
        message={
          <>
            This removes “{deleting?.title || 'New conversation'}” from your list.
            {actionError ? <ErrorNote error={actionError} className="mt-2" /> : null}
          </>
        }
        confirmLabel="Delete"
        variant="danger"
        loading={busy}
      />
    </div>
  );
}
