interface GoogleAccountsId {
  initialize: (config: {
    client_id: string;
    callback: (response: { credential: string; select_by?: string }) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }) => void;
  renderButton: (element: HTMLElement, config: Record<string, unknown>) => void;
  prompt: (callback?: (notification: unknown) => void) => void;
  disableAutoSelect: () => void;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: GoogleAccountsId;
      };
    };
  }
}

export {};
