'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Globe, Lock, Mail, ShieldCheck } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { ErrorNote } from '@/components/app/ErrorNote';
import { ThemeToggle } from '@/components/app/ThemeToggle';
import {
  AuroraBackdrop,
  BlurText,
  BorderBeam,
  InteractiveGrid,
  SopFlowVisual,
  SpotlightCard,
} from '@/components/effects';
import { BrandMark, CollapsiblePanel } from '@/components/motion/Primitives';
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
        gsi.renderButton(buttonHost.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          width: 300,
          locale: 'en',
        });
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
    <main className="relative flex min-h-dvh flex-col overflow-hidden bg-background lg:flex-row">
      {/* Left Ink & Teal Visual Showcase Rail — low text, high visual clarity */}
      <section className="relative flex flex-col justify-between overflow-hidden bg-[#0b1720] px-6 py-8 text-slate-100 sm:px-8 sm:py-9 lg:w-[56%] lg:px-10 lg:py-12 xl:px-14 2xl:px-20">
        <AuroraBackdrop variant="ink" />
        <InteractiveGrid
          squareSize={46}
          borderColor="rgba(148, 163, 184, 0.1)"
          hoverFillColor="rgba(20, 184, 166, 0.18)"
        />

        <div className="relative z-10 flex items-center gap-3">
          <BrandMark className="h-9 w-9 rounded-xl" />
          <span className="text-lg font-bold tracking-tight text-white">SOPilot</span>
        </div>

        <div className="relative z-10 my-8 w-full max-w-4xl space-y-6 lg:space-y-8">
          <BlurText
            as="h1"
            text="Ask SOPs. Trust every citation."
            className="text-3xl font-bold leading-[1.12] tracking-tight text-white sm:text-4xl lg:text-[2.6rem] xl:text-5xl"
          />

          <SopFlowVisual />
        </div>

        <div className="relative z-10 flex flex-wrap items-center gap-2.5 text-xs text-slate-300">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">
            <Globe size={12} aria-hidden className="text-teal-400" /> EN / VI
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">
            <Lock size={12} aria-hidden className="text-teal-400" /> Tenant RLS
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">
            <ShieldCheck size={12} aria-hidden className="text-teal-400" /> Verified Highlights
          </span>
        </div>
      </section>

      {/* Right Sign-in Card Panel */}
      <section className="relative flex flex-1 items-center justify-center p-6 sm:p-10 lg:p-14">
        <AuroraBackdrop variant="subtle" />
        <div className="absolute right-5 top-5 z-20">
          <ThemeToggle />
        </div>

        <div className="relative z-10 w-full max-w-md">
          <SpotlightCard
            overlay={<BorderBeam durationSec={9} rx={16} />}
            className="rounded-2xl p-7 sm:p-8"
          >
            <div className="flex items-center gap-2.5">
              <BrandMark className="h-8 w-8 lg:hidden" />
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-foreground">Welcome back</h2>
                <p className="mt-1 text-sm text-muted-foreground">Sign in to your SOP workspace.</p>
              </div>
            </div>

            <div className="mt-7 space-y-4">
              {clientId ? (
                <div ref={buttonHost} className="flex min-h-11 items-center justify-center" />
              ) : (
                <p className="rounded-xl border border-warning/25 bg-warning-soft p-3 text-xs text-warning-foreground">
                  Google sign-in is not configured (NEXT_PUBLIC_GOOGLE_CLIENT_ID is empty at build time).
                </p>
              )}

              {googleError ? (
                <p role="alert" className="text-xs text-danger-foreground">
                  {googleError}
                </p>
              ) : null}
              {error ? <ErrorNote error={error} /> : null}

              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-[11px] uppercase tracking-wider">
                  <span className="bg-card px-2.5 text-muted-foreground">Local dev</span>
                </div>
              </div>

              <button
                type="button"
                className="flex w-full cursor-pointer items-center justify-between rounded-xl border border-dashed border-border px-3.5 py-2.5 text-sm font-medium text-primary-strong transition-colors hover:border-primary/40 hover:bg-primary-soft/50 focus-visible:outline-2 focus-visible:outline-ring"
                onClick={() => setShowDev((v) => !v)}
                aria-expanded={showDev}
              >
                <span className="inline-flex items-center gap-2">
                  <Mail size={15} aria-hidden /> Dev sign-in (local only)
                </span>
                <span className="text-xs text-muted-foreground">{showDev ? 'Hide' : 'Expand'}</span>
              </button>

              <CollapsiblePanel open={showDev}>
                <form onSubmit={submitDev} className="space-y-3 pt-1">
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
              </CollapsiblePanel>
            </div>
          </SpotlightCard>
        </div>
      </section>
    </main>
  );
}
