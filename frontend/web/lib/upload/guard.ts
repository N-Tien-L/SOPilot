// In-app exits that cancel the batch (workspace switch, sign-out) ask first while bytes are still
// being sent or waiting; the browser's leave-page warning only covers closing or reloading the tab.

import { useUploadStore } from '@/store/upload-store';
import { hasPendingBytes } from './queue';

export const DISCARD_UPLOADS_PROMPT = 'Files are still being uploaded. Continuing cancels them. Continue?';

/** True when it is fine to continue: nothing pending, or the user agreed to cancel it. */
export function confirmDiscardUploads(): boolean {
  if (!hasPendingBytes(useUploadStore.getState().queue)) return true;
  return window.confirm(DISCARD_UPLOADS_PROMPT);
}
