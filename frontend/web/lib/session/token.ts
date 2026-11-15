// The access token lives in this module variable only: never in localStorage, sessionStorage,
// a URL or a log (frontend-nfrs S1). A page reload loses it; the HttpOnly cookie restores it.

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
