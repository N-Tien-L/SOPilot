import { create } from 'zustand';

interface InspectorState {
  /** Whether the right-hand Pipeline Inspector panel is expanded. */
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  reset: () => void;
}

export const useInspectorStore = create<InspectorState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set((s) => ({ open: !s.open })),
  reset: () => set({ open: false }),
}));

export function resetInspector(): void {
  useInspectorStore.getState().reset();
}
