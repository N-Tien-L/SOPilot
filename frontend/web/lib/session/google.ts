// Google Identity Services loader (the provider the stack already uses for sign-in, ADR-005).
// Only the ID token goes to core-api; nothing is stored here.

const GIS_SRC = 'https://accounts.google.com/gsi/client';

interface GoogleIdApi {
  initialize: (config: {
    client_id: string;
    nonce: string;
    callback: (response: { credential?: string }) => void;
    ux_mode?: 'popup';
  }) => void;
  renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdApi } };
  }
}

let loading: Promise<GoogleIdApi> | null = null;

export function googleClientId(): string {
  return process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? '';
}

export function loadGoogle(): Promise<GoogleIdApi> {
  if (window.google) return Promise.resolve(window.google.accounts.id);
  loading ??= new Promise<GoogleIdApi>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = GIS_SRC;
    script.async = true;
    script.onload = () => {
      if (window.google) resolve(window.google.accounts.id);
      else reject(new Error('google-unavailable'));
    };
    script.onerror = () => {
      loading = null;
      reject(new Error('google-unavailable'));
    };
    document.head.appendChild(script);
  });
  return loading;
}

export type { GoogleIdApi };
