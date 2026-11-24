// Per-browser choice of the reranker for chat questions (V2-48). Not a secret, so localStorage is
// fine (only tokens are forbidden there). The key holds "off" or is absent; absent means on.

export const RERANK_PREFERENCE_KEY = 'sopilot.chat.rerank';

export interface PreferenceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function defaultStorage(): PreferenceStorage | undefined {
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

/** True (on) unless the user switched it off; never throws. */
export function readRerankPreference(storage: PreferenceStorage | undefined = defaultStorage()): boolean {
  try {
    return storage?.getItem(RERANK_PREFERENCE_KEY) !== 'off';
  } catch {
    return true;
  }
}

/** The value to send: undefined (server default) when no reranker is available, else the choice. */
export function effectiveRerank(available: boolean, on: boolean): boolean | undefined {
  return available ? on : undefined;
}

export function writeRerankPreference(
  on: boolean,
  storage: PreferenceStorage | undefined = defaultStorage(),
): void {
  try {
    if (!storage) return;
    if (on) storage.removeItem(RERANK_PREFERENCE_KEY);
    else storage.setItem(RERANK_PREFERENCE_KEY, 'off');
  } catch {
    // Storage is unavailable (private mode, quota); the choice then lasts for this page only.
  }
}
