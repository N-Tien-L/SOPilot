'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ErrorNote } from '@/components/app/ErrorNote';
import { useAction } from '@/components/admin/useAction';
import { Button } from '@/components/ui';
import { acceptInvitation } from '@/lib/api/endpoints';
import { clearInviteToken, holdInviteToken, peekInviteToken, readInviteToken } from '@/lib/admin/invite';
import { adoptSession } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { ROLE_LABEL } from '@/lib/admin/members';
import { useSessionStore } from '@/store/session-store';

// The link from an invitation is /invite#token=<secret>. The token is read from the fragment once
// and removed from the address bar; it is kept in memory only (a reload asks for the link again).
// Accepting needs a signed-in account; the server checks that the account matches the invitation.

export default function InvitePage() {
  const router = useRouter();
  const status = useSessionStore((s) => s.status);
  const pending = useSessionStore((s) => s.pendingInvitations);
  // The token is taken from the fragment on first render and kept in memory. Nothing renders it
  // before the session is known, so the server-rendered markup does not depend on it.
  const [token] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const fromLink = readInviteToken(window.location.hash);
    if (fromLink) holdInviteToken(fromLink);
    return fromLink ?? peekInviteToken();
  });
  // Remove the secret from the address bar after Next has finished syncing the URL (doing it while
  // rendering is overwritten by the router).
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
  }, []);
  const { run, busy, error } = useAction();

  async function accept(input: { invitationToken: string } | { invitationId: string }) {
    if (!confirmDiscardUploads()) return;
    let payload: Awaited<ReturnType<typeof acceptInvitation>> | null = null;
    const ok = await run(async () => {
      payload = await acceptInvitation(input);
    });
    if (ok && payload) {
      clearInviteToken();
      adoptSession(payload);
      router.replace('/chat');
    }
  }

  let body: React.ReactNode;
  if (status === 'unknown') {
    body = <p className="text-sm text-muted-foreground">Loading…</p>;
  } else if (status === 'unreachable') {
    body = <p role="alert" className="text-sm">The server could not be reached. Reload to try again.</p>;
  } else if (status === 'anonymous') {
    body = token ? (
      <div className="space-y-4">
        <p className="text-sm">You have been invited to a SOPilot workspace. Sign in with the invited account to join it.</p>
        <Button variant="primary" onClick={() => router.push('/login')}>
          Sign in to accept
        </Button>
      </div>
    ) : (
      <p className="text-sm text-muted-foreground">
        This page needs the invitation link you were sent. Open that link again, or <Link href="/login" className="underline">sign in</Link>.
      </p>
    );
  } else {
    body = (
      <div className="space-y-6">
        {token ? (
          <section aria-labelledby="link-invite" className="space-y-3">
            <h2 id="link-invite" className="text-lg font-semibold">Invitation link</h2>
            <p className="text-sm text-muted-foreground">Accepting adds you to the workspace and switches this session to it.</p>
            <Button variant="primary" loading={busy} onClick={() => void accept({ invitationToken: token })}>
              Accept invitation
            </Button>
          </section>
        ) : null}
        {pending.length > 0 ? (
          <section aria-labelledby="pending-invites" className="space-y-3">
            <h2 id="pending-invites" className="text-lg font-semibold">Invitations for your account</h2>
            <ul className="divide-y divide-border rounded-lg border border-border bg-card text-sm">
              {pending.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2">
                  <span>
                    <span className="font-medium">{p.workspaceName}</span>
                    <span className="ml-2 text-xs text-muted-foreground">as {ROLE_LABEL[p.role] ?? p.role}</span>
                  </span>
                  <Button size="sm" variant="primary" disabled={busy} onClick={() => void accept({ invitationId: p.id })}>
                    Accept
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {!token && pending.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No invitation to accept. If you were sent a link, open it again. <Link href="/chat" className="underline">Back to chat</Link>
          </p>
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
      </div>
    );
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col justify-center p-8">
      <h1 className="text-2xl font-bold">Join a workspace</h1>
      <div className="mt-6">{body}</div>
    </main>
  );
}
