// The invitation link is `/invite#token=<secret>`. The token stays in the URL fragment (never sent
// to a server) and is read once, then removed from the address bar. If the visitor has to sign in
// first it is kept in memory only, never in storage.

export function readInviteToken(hash: string): string | null {
  const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
  const token = params.get('token')?.trim();
  return token ? token : null;
}

let held: string | null = null;

export function holdInviteToken(token: string): void {
  held = token;
}

export function peekInviteToken(): string | null {
  return held;
}

export function clearInviteToken(): void {
  held = null;
}
