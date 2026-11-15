'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { Button, Input } from '@/components/ui';
import { describeError } from '@/lib/api/errors';
import { devLogin } from '@/lib/session/auth';
import { useSessionStore } from '@/store/session-store';

// Dev login only (core-api serves it in the local and test profiles). Google sign-in is V2-15.
export default function LoginPage() {
  const router = useRouter();
  const status = useSessionStore((s) => s.status);
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; traceId: string | null } | null>(null);

  useEffect(() => {
    if (status === 'authenticated') router.replace('/');
  }, [status, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await devLogin(email.trim());
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-xl font-semibold">Sign in</h1>
      <p className="mt-1 text-sm text-gray-500">Development sign-in (local stack only).</p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <Input
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" loading={busy} fullWidth>
          Sign in
        </Button>
      </form>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error.message}
          {error.traceId ? <span className="block text-xs text-gray-500">Trace: {error.traceId}</span> : null}
        </p>
      ) : null}
    </main>
  );
}
