'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui';
import { describeError } from '@/lib/api/errors';
import { restoreSession, signOut } from '@/lib/session/auth';
import { useSessionStore } from '@/store/session-store';

// Minimal shell (V2-38): a workspace-aware empty home. Navigation, the workspace picker and chat
// belong to V2-15.
export default function HomePage() {
  const router = useRouter();
  const status = useSessionStore((s) => s.status);
  const user = useSessionStore((s) => s.user);
  const workspace = useSessionStore((s) => s.workspace);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'anonymous') router.replace('/login');
  }, [status, router]);

  if (status === 'unreachable') {
    return (
      <main className="p-8 text-sm">
        <p role="alert">The server could not be reached. Your session is kept; try again.</p>
        <div className="mt-4">
          <Button variant="outline" onClick={() => void restoreSession()}>
            Retry
          </Button>
        </div>
      </main>
    );
  }

  if (status !== 'authenticated' || !user || !workspace) {
    return <main className="p-8 text-sm text-gray-500">Loading…</main>;
  }

  async function handleSignOut() {
    try {
      await signOut();
    } catch (e) {
      setError(describeError(e).message);
    }
  }

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-xl font-semibold">{workspace.name}</h1>
      <p className="mt-1 text-sm text-gray-500">
        Signed in as {user.displayName} ({user.email}) · role {workspace.role}
      </p>
      <p className="mt-6 text-sm">Nothing here yet.</p>
      {error ? <p role="alert" className="mt-4 text-sm text-red-600">{error}</p> : null}
      <div className="mt-6">
        <Button variant="outline" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </main>
  );
}
