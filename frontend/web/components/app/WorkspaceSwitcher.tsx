'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import * as Popover from '@radix-ui/react-popover';
import { Check, ChevronsUpDown, LayoutGrid, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { switchWorkspace } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
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

  async function choose(id: string, name: string) {
    setOpen(false);
    if (id === workspace?.id) return;
    if (!confirmDiscardUploads()) return;
    setSwitchError(null);
    try {
      await switchWorkspace(id);
      toast.success(`Switched to ${name}`);
      router.push('/chat');
    } catch (e) {
      setSwitchError(e);
    }
  }

  return (
    <div className="relative">
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-haspopup="listbox"
            aria-expanded={open}
            className="inline-flex h-9 max-w-[10.5rem] cursor-pointer items-center gap-2 rounded-xl border border-border bg-card px-2.5 text-sm font-semibold text-foreground shadow-2xs transition-colors hover:border-border-strong hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:max-w-[15rem] sm:px-3"
          >
            <span className="h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
            <span className="truncate">{workspace?.name ?? 'Workspace'}</span>
            <ChevronsUpDown size={13} aria-hidden className="shrink-0 text-muted-foreground" />
          </button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            align="start"
            sideOffset={6}
            className="z-50 w-72 rounded-2xl border border-border bg-card-elevated p-1.5 shadow-[var(--shadow-lg)] focus:outline-none"
          >
            {isError ? <ErrorNote error={error} className="m-1" /> : null}
            <p className="px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Workspaces
            </p>
            <ul role="listbox" aria-label="Workspaces" className="max-h-64 space-y-0.5 overflow-auto">
              {(data ?? []).map((w) => (
                <li key={w.id} role="option" aria-selected={w.id === workspace?.id}>
                  <button
                    type="button"
                    onClick={() => void choose(w.id, w.name)}
                    className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted"
                  >
                    <div className="min-w-0">
                      <span className="block truncate font-medium text-foreground">{w.name}</span>
                      <span className="block text-[11px] text-muted-foreground">
                        {w.kind} · {w.role}
                      </span>
                    </div>
                    {w.id === workspace?.id ? (
                      <Check size={14} aria-label="Current" className="shrink-0 text-primary" />
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-1.5 border-t border-border pt-1.5">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setCreating(true);
                }}
                className="flex w-full cursor-pointer items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-semibold text-primary-strong transition-colors hover:bg-primary-soft/60"
              >
                <Plus size={14} aria-hidden /> Create workspace
              </button>
              <Link
                href="/workspaces"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <LayoutGrid size={13} aria-hidden /> All workspaces
              </Link>
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>

      {switchError ? <ErrorNote error={switchError} className="absolute left-0 z-40 mt-1.5 w-72" /> : null}
      <CreateWorkspaceModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
