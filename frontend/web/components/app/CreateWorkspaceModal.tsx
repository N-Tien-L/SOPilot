'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Modal } from '@/components/ui';
import { createWorkspace } from '@/lib/api/endpoints';
import { adoptSession } from '@/lib/session/auth';
import { ErrorNote } from './ErrorNote';

export function CreateWorkspaceModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      adoptSession(await createWorkspace(name.trim()));
      setName('');
      onClose();
      router.push('/chat');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create workspace" description="A new team workspace. You become its owner.">
      <form onSubmit={submit} className="space-y-4">
        <Input label="Name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy} disabled={name.trim().length === 0}>
            Create
          </Button>
        </div>
      </form>
    </Modal>
  );
}
