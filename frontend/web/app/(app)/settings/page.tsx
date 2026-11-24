'use client';

import { useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, HardDrive, LogOut, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { ErrorNote } from '@/components/app/ErrorNote';
import { CountUp } from '@/components/effects';
import { FadeIn } from '@/components/motion/Primitives';
import { Button, ConfirmDialog, Input, Modal, PageHeader, Skeleton, StatCard } from '@/components/ui';
import { deleteWorkspace, leaveWorkspace, renameWorkspace } from '@/lib/api/endpoints';
import { formatBytes } from '@/lib/chat/labels';
import { useInvalidate, useWorkspaceDetail } from '@/lib/query/hooks';
import { moveToAnotherWorkspace } from '@/lib/session/exit';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { useSessionStore } from '@/store/session-store';

export default function SettingsPage() {
  const router = useRouter();
  const workspace = useSessionStore((s) => s.workspace);
  const { data, isLoading, isError, error } = useWorkspaceDetail();
  const invalidate = useInvalidate();
  const [name, setName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [renameError, setRenameError] = useState<unknown>(null);
  const [leaving, setLeaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState('');
  const [exitError, setExitError] = useState<unknown>(null);
  // Leave and delete cannot be repeated once they succeeded; a failed move only retries the move.
  const actionDone = useRef(false);

  if (!workspace) return null;
  if (isLoading)
    return (
      <div className="mx-auto max-w-2xl p-6">
        <Skeleton count={3} height={56} />
      </div>
    );
  if (isError || !data)
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorNote error={error} />
      </div>
    );

  const isOwner = data.role === 'OWNER';
  const isPersonal = data.kind === 'PERSONAL';
  const currentName = name ?? data.name;

  async function rename(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setSaved(false);
    setRenameError(null);
    try {
      await renameWorkspace(currentName.trim());
      // The workspace list and the shell read the name from the session/list; refresh both.
      await invalidate('workspace');
      await invalidate('workspaces');
      useSessionStore.getState().set({
        user: useSessionStore.getState().user!,
        workspace: { ...workspace!, name: currentName.trim() },
        pendingInvitations: useSessionStore.getState().pendingInvitations,
      });
      setName(null);
      setSaved(true);
      toast.success('Workspace renamed');
    } catch (e) {
      setRenameError(e);
    } finally {
      setBusy(false);
    }
  }

  async function exit(action: () => Promise<void>) {
    if (!confirmDiscardUploads()) return;
    setBusy(true);
    setExitError(null);
    try {
      if (!actionDone.current) {
        await action();
        actionDone.current = true;
      }
      await moveToAnotherWorkspace(data!.id);
      actionDone.current = false;
      setLeaving(false);
      setDeleting(false);
      router.push('/chat');
    } catch (e) {
      setExitError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <FadeIn>
        <PageHeader
          title="Workspace settings"
          description={`${isPersonal ? 'Personal workspace' : 'Team workspace'} · your role: ${data.role}`}
        />
      </FadeIn>

      <div className="grid gap-3 sm:grid-cols-2">
        <StatCard
          label="Documents"
          value={<CountUp to={data.documentCount} suffix={data.documentCount === 1 ? ' document' : ' documents'} />}
          icon={<FileText size={14} aria-hidden />}
        />
        <StatCard
          label="Storage used"
          value={formatBytes(data.bytesUsed)}
          hint="Stored in workspace bucket"
          icon={<HardDrive size={14} aria-hidden />}
        />
      </div>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-[var(--shadow-sm)]">
        <h2 className="text-base font-bold text-foreground">Name</h2>
        <form onSubmit={rename} className="mt-3 flex items-start gap-2">
          <div className="flex-1">
            <Input
              aria-label="Workspace name"
              value={currentName}
              maxLength={100}
              disabled={!isOwner}
              onChange={(e) => setName(e.target.value)}
              helperText={isOwner ? undefined : 'Only an owner can rename the workspace.'}
            />
          </div>
          {isOwner ? (
            <Button type="submit" loading={busy} disabled={currentName.trim().length === 0 || currentName.trim() === data.name}>
              Rename
            </Button>
          ) : null}
        </form>
        {saved ? (
          <p role="status" className="mt-2 text-xs font-medium text-success-foreground">
            Saved.
          </p>
        ) : null}
        {renameError ? <ErrorNote error={renameError} className="mt-2" /> : null}
      </section>

      {!isPersonal ? (
        <section className="rounded-2xl border border-border bg-card p-5 shadow-[var(--shadow-sm)]">
          <h2 className="text-base font-bold text-foreground">Leave workspace</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            You lose access to its documents and conversations. The last owner cannot leave.
          </p>
          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              icon={<LogOut size={14} aria-hidden />}
              onClick={() => {
                setExitError(null);
                setLeaving(true);
              }}
            >
              Leave workspace
            </Button>
          </div>
        </section>
      ) : null}

      {isOwner ? (
        <section className="rounded-2xl border border-danger/35 bg-danger-soft/60 p-5">
          <div className="flex items-center gap-2 text-danger-foreground">
            <ShieldAlert size={16} aria-hidden />
            <h2 className="text-base font-bold">Danger zone</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? 'A personal workspace cannot be deleted.'
              : 'Deleting removes the workspace, its documents and its members’ access.'}
          </p>
          <div className="mt-4">
            <Button
              variant="destructive"
              size="sm"
              disabled={isPersonal}
              onClick={() => {
                setTyped('');
                setExitError(null);
                setDeleting(true);
              }}
            >
              Delete workspace
            </Button>
          </div>
        </section>
      ) : null}

      <ConfirmDialog
        open={leaving}
        onClose={() => setLeaving(false)}
        onConfirm={() => void exit(leaveWorkspace)}
        title="Leave this workspace?"
        message={
          <>
            You will switch to another workspace.
            {exitError ? <ErrorNote error={exitError} className="mt-2" /> : null}
          </>
        }
        confirmLabel="Leave"
        variant="danger"
        loading={busy}
      />
      <Modal
        open={deleting}
        onClose={() => setDeleting(false)}
        title="Delete workspace"
        description={`Type “${data.name}” to confirm. This cannot be undone.`}
      >
        <div className="space-y-4">
          <Input aria-label="Workspace name to confirm" value={typed} onChange={(e) => setTyped(e.target.value)} />
          {exitError ? <ErrorNote error={exitError} /> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleting(false)}>
              Cancel
            </Button>
            <Button variant="destructive" loading={busy} disabled={typed !== data.name} onClick={() => void exit(deleteWorkspace)}>
              Delete workspace
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
