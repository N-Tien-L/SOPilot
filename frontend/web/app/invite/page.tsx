'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { MailCheck } from 'lucide-react';
import { toast } from 'sonner';
import { ErrorNote } from '@/components/app/ErrorNote';
import { ThemeToggle } from '@/components/app/ThemeToggle';
import { useAction } from '@/components/admin/useAction';
import { AuroraBackdrop, BorderBeam, SpotlightCard } from '@/components/effects';
import { BrandMark } from '@/components/motion/Primitives';
import { Button, Spinner } from '@/components/ui';
import { acceptInvitation } from '@/lib/api/endpoints';
import { clearInviteToken, holdInviteToken, peekInviteToken, readInviteToken } from '@/lib/admin/invite';
import { ApiError } from '@/lib/api/errors';
import { adoptSession, signOut } from '@/lib/session/auth';
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
  const email = useSessionStore((s) => s.user?.email ?? null);
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
      toast.success('Joined workspace');
      router.replace('/chat');
    }
  }

  // The link belongs to another account: sign out, keep the link in memory and go to the sign-in page.
  async function switchAccount() {
    const held = token;
    try {
      await signOut();
    } finally {
      if (held) holdInviteToken(held);
      router.replace('/login');
    }
  }

  const wrongAccount = error instanceof ApiError && error.code === 'INVITATION_EMAIL_MISMATCH';

  let body: React.ReactNode;
  if (status === 'unknown') {
    body = (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner size="sm" />
        <span>Loading…</span>
      </div>
    );
  } else if (status === 'unreachable') {
    body = <p role="alert" className="text-sm text-danger-foreground">The server could not be reached. Reload to try again.</p>;
  } else if (status === 'anonymous') {
    body = token ? (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          You have been invited to a SOPilot workspace. Sign in with the invited account to join it.
        </p>
        <Button variant="primary" fullWidth onClick={() => router.push('/login')}>
          Sign in to accept
        </Button>
      </div>
    ) : (
      <p className="text-sm text-muted-foreground">
        This page needs the invitation link you were sent. Open that link again, or{' '}
        <Link href="/login" className="font-semibold text-primary-strong underline underline-offset-2">
          sign in
        </Link>
        .
      </p>
    );
  } else {
    body = (
      <div className="space-y-6">
        {token ? (
          <section aria-labelledby="link-invite" className="space-y-3 rounded-xl border border-border bg-muted/45 p-4">
            <h2 id="link-invite" className="text-base font-semibold text-foreground">
              Invitation link
            </h2>
            <p className="text-xs text-muted-foreground">
              Accepting adds you to the workspace and switches this session to it.
            </p>
            <Button variant="primary" loading={busy} onClick={() => void accept({ invitationToken: token })}>
              Accept invitation
            </Button>
          </section>
        ) : null}
        {pending.length > 0 ? (
          <section aria-labelledby="pending-invites" className="space-y-3">
            <h2 id="pending-invites" className="text-base font-semibold text-foreground">
              Invitations for your account
            </h2>
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background text-sm">
              {pending.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-foreground">{p.workspaceName}</span>
                    <span className="text-xs text-muted-foreground">as {ROLE_LABEL[p.role] ?? p.role}</span>
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
            No invitation to accept. If you were sent a link, open it again.{' '}
            <Link href="/chat" className="font-semibold text-primary-strong underline underline-offset-2">
              Back to chat
            </Link>
          </p>
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        {wrongAccount ? (
          <div className="space-y-2.5 rounded-xl border border-border bg-muted/60 p-4 text-sm">
            <p className="text-foreground">
              You are signed in as <strong>{email ?? 'this account'}</strong>. Sign in with the account the invitation was sent to.
            </p>
            <Button variant="secondary" size="sm" onClick={() => void switchAccount()}>
              Sign out and use another account
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-background p-6">
      <AuroraBackdrop variant="subtle" />
      <div className="absolute right-5 top-5 z-20">
        <ThemeToggle />
      </div>

      <div className="relative z-10 w-full max-w-lg">
        <SpotlightCard
          overlay={<BorderBeam durationSec={10} rx={16} />}
          className="rounded-2xl p-7 sm:p-8"
        >
          <div className="flex items-center gap-3">
            <BrandMark className="h-9 w-9" />
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-semibold text-primary-strong">
              <MailCheck size={13} aria-hidden /> Workspace invitation
            </span>
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-foreground">Join a workspace</h1>
          <div className="mt-5">{body}</div>
        </SpotlightCard>
      </div>
    </main>
  );
}
