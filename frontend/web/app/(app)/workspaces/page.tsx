'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Check, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { CreateWorkspaceModal } from '@/components/app/CreateWorkspaceModal';
import { ErrorNote } from '@/components/app/ErrorNote';
import { SpotlightCard } from '@/components/effects';
import { FadeIn } from '@/components/motion/Primitives';
import { Badge, Button, PageHeader, Skeleton } from '@/components/ui';
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

  async function choose(id: string, name: string) {
    setSwitchError(null);
    if (id !== current?.id && !confirmDiscardUploads()) return;
    try {
      if (id !== current?.id) {
        await switchWorkspace(id);
        toast.success(`Switched to ${name}`);
      }
      router.push('/chat');
    } catch (e) {
      setSwitchError(e);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <FadeIn>
        <PageHeader
          title="Choose a workspace"
          description="Each workspace has its own documents, members and conversations."
          actions={
            <Button variant="primary" icon={<Plus size={15} aria-hidden />} onClick={() => setCreating(true)}>
              Create workspace
            </Button>
          }
        />
      </FadeIn>

      {isLoading ? <Skeleton count={3} height={72} /> : null}
      {isError ? <ErrorNote error={error} /> : null}
      {switchError ? <ErrorNote error={switchError} /> : null}

      <ul className="grid gap-3 sm:grid-cols-2">
        {(data ?? []).map((w, idx) => {
          const isCurrent = w.id === current?.id;
          return (
            <li key={w.id}>
              <FadeIn delay={0.04 * idx}>
                <SpotlightCard className={isCurrent ? 'border-primary/50' : ''}>
                  <button
                    type="button"
                    onClick={() => void choose(w.id, w.name)}
                    className="flex w-full cursor-pointer flex-col items-start gap-2 p-5 text-left focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <div className="flex w-full items-center justify-between gap-2">
                      <span className="truncate text-base font-bold text-foreground">{w.name}</span>
                      {isCurrent ? (
                        <Badge variant="default" icon={<Check size={11} aria-hidden />}>
                          Current
                        </Badge>
                      ) : null}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {w.kind} · {w.role}
                    </span>
                  </button>
                </SpotlightCard>
              </FadeIn>
            </li>
          );
        })}
      </ul>

      <CreateWorkspaceModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
