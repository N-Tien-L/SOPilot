'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Check, ChevronsUpDown, Plus } from 'lucide-react';
import { switchWorkspace } from '@/lib/session/auth';
import { useWorkspaces } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { CreateWorkspaceModal } from './CreateWorkspaceModal';
import { ErrorNote } from './ErrorNote';

export function WorkspaceSwitcher() {
  const router = useRouter();
  const workspace = useSessionStore((s) => s.workspace);
  const { data, isError, error } = useWorkspaces();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [switchError, setSwitchError] = useState<unknown>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent) {
        if (e.key === 'Escape') setOpen(false);
      } else if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  async function choose(id: string) {
    setOpen(false);
    if (id === workspace?.id) return;
    setSwitchError(null);
    try {
      await switchWorkspace(id);
      router.push('/chat');
    } catch (e) {
      setSwitchError(e);
    }
  }

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex max-w-[16rem] items-center gap-2 rounded-md border border-border bg-muted px-3 py-1.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <span className="truncate">{workspace?.name ?? 'Workspace'}</span>
        <ChevronsUpDown size={14} aria-hidden className="shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <div className="absolute left-0 z-30 mt-1 w-72 rounded-lg border border-border bg-card p-1 shadow-lg">
          {isError ? <ErrorNote error={error} className="p-2" /> : null}
          <ul role="listbox" aria-label="Workspaces" className="max-h-64 overflow-auto">
            {(data ?? []).map((w) => (
              <li key={w.id} role="option" aria-selected={w.id === workspace?.id}>
                <button
                  type="button"
                  onClick={() => void choose(w.id)}
                  className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
                >
                  <span className="truncate">{w.name}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    {w.role}
                    {w.id === workspace?.id ? <Check size={14} aria-label="Current" /> : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-1 border-t border-border pt-1">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setCreating(true);
              }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-primary-strong hover:bg-muted"
            >
              <Plus size={14} aria-hidden /> Create workspace
            </button>
            <Link
              href="/workspaces"
              onClick={() => setOpen(false)}
              className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
            >
              All workspaces
            </Link>
          </div>
        </div>
      ) : null}
      {switchError ? <ErrorNote error={switchError} className="absolute mt-1" /> : null}
      <CreateWorkspaceModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
