import { create } from 'zustand';
import { emptyQueue, type UploadQueue, type VersionTarget } from '@/lib/upload/queue';

// Memory only. The queue itself is plain data (names, sizes, states); the File objects and the
// abort controllers cannot live in state, so they are kept beside it by item id.

export type UploadDialogMode = 'new' | 'version';

interface UploadState {
  queue: UploadQueue;
  dialogOpen: boolean;
  dialogMode: UploadDialogMode;
  targetDocument: VersionTarget | null;
  /** One line about the last add (for example "3 files were not added"). */
  notice: string | null;
  update: (change: (queue: UploadQueue) => UploadQueue) => void;
  setDialogOpen: (open: boolean) => void;
  openDialog: (mode: UploadDialogMode, target?: VersionTarget | null) => void;
  setDialogMode: (mode: UploadDialogMode) => void;
  setTargetDocument: (target: VersionTarget | null) => void;
  setNotice: (notice: string | null) => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  queue: emptyQueue,
  dialogOpen: false,
  dialogMode: 'new',
  targetDocument: null,
  notice: null,
  update: (change) => set((state) => {
    const queue = change(state.queue);
    return queue === state.queue ? state : { queue };
  }),
  setDialogOpen: (dialogOpen) => set(dialogOpen ? { dialogOpen } : { dialogOpen, targetDocument: null }),
  openDialog: (dialogMode, target = null) => set({ dialogOpen: true, dialogMode, targetDocument: target }),
  setDialogMode: (dialogMode) => set({ dialogMode }),
  setTargetDocument: (targetDocument) => set({ targetDocument }),
  setNotice: (notice) => set({ notice }),
}));

const files = new Map<string, File>();
const controllers = new Map<string, AbortController>();
/** Consecutive failed status reads per document id (see pollProcessing). */
export const pollErrors = new Map<string, number>();

export const rememberFile = (id: string, file: File): void => void files.set(id, file);
export const fileFor = (id: string): File | undefined => files.get(id);
export const forgetFile = (id: string): void => void files.delete(id);

export function trackUpload(id: string, controller: AbortController): () => void {
  controllers.set(id, controller);
  return () => {
    if (controllers.get(id) === controller) controllers.delete(id);
  };
}

/** R7: a workspace switch cancels in-flight uploads and forgets the whole batch. */
export function resetUploadState(): void {
  for (const controller of controllers.values()) controller.abort();
  controllers.clear();
  files.clear();
  pollErrors.clear();
  useUploadStore.setState({ queue: emptyQueue, notice: null, dialogOpen: false, dialogMode: 'new', targetDocument: null });
}
