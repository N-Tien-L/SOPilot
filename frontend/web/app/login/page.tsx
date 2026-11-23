'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button, Input } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import { devLogin, googleLogin, requestNonce } from '@/lib/session/auth';
import { peekInviteToken } from '@/lib/admin/invite';
import { googleClientId, loadGoogle } from '@/lib/session/google';
import { useSessionStore } from '@/store/session-store';

export default function LoginPage() {
  const router = useRouter();
  const status = useSessionStore((s) => s.status);
  const clientId = googleClientId();
  const buttonHost = useRef<HTMLDivElement>(null);
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [showDev, setShowDev] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    // A visitor who came from an invitation link goes back to accept it.
    if (status === 'authenticated') router.replace(peekInviteToken() ? '/invite' : '/chat');
  }, [status, router]);

  useEffect(() => {
    if (!clientId || status === 'authenticated') return;
    let cancelled = false;
    // The nonce cookie lives 5 minutes and is single purpose: after any failed attempt, fetch a
    // fresh nonce and initialise Google again so the button keeps working without a reload.
    async function setup(): Promise<void> {
      try {
        const nonce = await requestNonce();
        const gsi = await loadGoogle();
        if (cancelled || !buttonHost.current) return;
        gsi.initialize({
          client_id: clientId,
          nonce,
          ux_mode: 'popup',
          callback: (response) => {
            if (!response.credential) return;
            setError(null);
            googleLogin(response.credential).catch((e: unknown) => {
              setError(e);
              void setup();
            });
          },
        });
        gsi.renderButton(buttonHost.current, { theme: 'outline', size: 'large', text: 'signin_with', width: 280, locale: 'en' });
      } catch {
        if (!cancelled) setGoogleError('Google sign-in could not be loaded. Check your connection and reload.');
      }
    }
    let lastSetup = Date.now();
    const refresh = () => {
      lastSetup = Date.now();
      return setup();
    };
    void refresh();
    // A tab left in the background past the nonce lifetime gets a fresh nonce when it is shown again.
    const onVisible = () => {
      if (document.visibilityState === 'visible' && Date.now() - lastSetup > 4 * 60 * 1000) void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [clientId, status]);

  async function submitDev(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await devLogin(email.trim());
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center p-8">
      <h1 className="text-3xl font-bold">SOPilot</h1>
      <p className="mt-1 text-muted-foreground">Ask your SOPs. Get cited answers.</p>
      <div className="mt-8 space-y-4">
        {clientId ? (
          <div ref={buttonHost} className="min-h-10" />
        ) : (
          <p className="rounded-md bg-warning-soft p-3 text-sm text-warning-foreground">
            Google sign-in is not configured (NEXT_PUBLIC_GOOGLE_CLIENT_ID is empty at build time).
          </p>
        )}
        {googleError ? (
          <p role="alert" className="text-sm text-danger-foreground">
            {googleError}
          </p>
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        <button
          type="button"
          className="text-sm text-primary-strong underline underline-offset-2"
          onClick={() => setShowDev((v) => !v)}
          aria-expanded={showDev}
        >
          Dev sign-in (local only)
        </button>
        {showDev ? (
          <form onSubmit={submitDev} className="space-y-3">
            <Input
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              aria-label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button type="submit" loading={busy} fullWidth>
              Sign in
            </Button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
