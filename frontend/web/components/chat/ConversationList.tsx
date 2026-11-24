'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
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
  const { data, isLoading, isError, error, refetch } = useConversations();
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
      toast.success('Conversation renamed');
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
      toast.info('Conversation deleted');
      setDeleting(null);
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-0">
      <div className="flex items-center justify-between px-2.5 pb-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted">
          Conversations
        </span>
        <Link
          href="/chat"
          aria-label="New chat"
          title="New chat"
          className="rounded-lg p-1 text-sidebar-muted transition-colors hover:bg-white/10 hover:text-sidebar-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          <Plus size={15} aria-hidden />
        </Link>
      </div>
      {isLoading ? <p className="px-2.5 py-1 text-xs text-sidebar-muted">Loading…</p> : null}
      {isError ? (
        <ErrorNote
          error={error}
          onRetry={() => void refetch()}
          className="mx-1 my-1 border-danger/40 bg-danger/15 !text-danger-soft"
        />
      ) : null}
      {data && data.length === 0 ? (
        <p className="px-2.5 py-1 text-xs text-sidebar-muted/80">No conversations yet.</p>
      ) : null}
      <ul className="space-y-0.5">
        {(data ?? []).map((c) => {
          const active = c.id === activeId;
          return (
            <li key={c.id} className="group relative">
              <Link
                href={`/chat/${c.id}`}
                aria-current={active ? 'page' : undefined}
                className={`block truncate rounded-lg py-1.5 pl-2.5 pr-14 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-ring ${
                  active
                    ? 'bg-white/12 font-medium text-sidebar-foreground'
                    : 'text-sidebar-muted hover:bg-white/[0.06] hover:text-sidebar-foreground'
                }`}
              >
                {c.title || 'New conversation'}
              </Link>
              <span className="absolute inset-y-0 right-1 hidden items-center gap-0.5 group-focus-within:flex group-hover:flex">
                <button
                  type="button"
                  aria-label={`Rename ${c.title || 'conversation'}`}
                  className="cursor-pointer rounded-md p-1 text-sidebar-muted transition-colors hover:bg-white/15 hover:text-sidebar-foreground"
                  onClick={() => {
                    setActionError(null);
                    setTitle(c.title ?? '');
                    setRenaming(c);
                  }}
                >
                  <Pencil size={12} aria-hidden />
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${c.title || 'conversation'}`}
                  className="cursor-pointer rounded-md p-1 text-sidebar-muted transition-colors hover:bg-white/15 hover:text-sidebar-foreground"
                  onClick={() => {
                    setActionError(null);
                    setDeleting(c);
                  }}
                >
                  <Trash2 size={12} aria-hidden />
                </button>
              </span>
            </li>
          );
        })}
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
