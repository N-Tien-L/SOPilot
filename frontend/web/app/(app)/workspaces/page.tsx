'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Plus } from 'lucide-react';
import { CreateWorkspaceModal } from '@/components/app/CreateWorkspaceModal';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Button, Skeleton } from '@/components/ui';
import { useWorkspaces } from '@/lib/query/hooks';
import { switchWorkspace } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { useSessionStore } from '@/store/session-store';

export default function WorkspacesPage() {
  const router = useRouter();
  const current = useSessionStore((s) => s.workspace);
  const { data, isLoading, isError, error } = useWorkspaces();
  const [creating, setCreating] = useState(false);
  const [switchError, setSwitchError] = useState<unknown>(null);

  async function choose(id: string) {
    setSwitchError(null);
    if (id !== current?.id && !confirmDiscardUploads()) return;
    try {
      if (id !== current?.id) await switchWorkspace(id);
      router.push('/chat');
    } catch (e) {
      setSwitchError(e);
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-semibold">Choose a workspace</h1>
      <p className="mt-1 text-sm text-muted-foreground">Each workspace has its own documents, members and conversations.</p>
      {isLoading ? <Skeleton count={3} height={56} /> : null}
      {isError ? <ErrorNote error={error} className="mt-4" /> : null}
      {switchError ? <ErrorNote error={switchError} className="mt-4" /> : null}
      <ul className="mt-6 space-y-2">
        {(data ?? []).map((w) => (
          <li key={w.id}>
            <button
              type="button"
              onClick={() => void choose(w.id)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-4 py-3 text-left hover:border-primary focus-visible:outline-2 focus-visible:outline-ring"
            >
              <span className="font-medium">{w.name}</span>
              <span className="text-xs text-muted-foreground">
                {w.kind} · {w.role}
                {w.id === current?.id ? ' · current' : ''}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-6">
        <Button variant="outline" icon={<Plus size={14} aria-hidden />} onClick={() => setCreating(true)}>
          Create workspace
        </Button>
      </div>
      <CreateWorkspaceModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
