export { ToastProvider, useToast } from './ToastContext';
export type { Toast, ToastType } from './ToastContext';
export { ToastContainer } from './ToastContainer';
import type { ToastType } from './ToastContext';

const TOAST_EVENT = 'poliwise-toast';

// Singleton toast instance for use outside React hooks
export const toast = {
  success: (message: string) => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { message, type: 'success' as ToastType } }));
    }
  },
  error: (message: string) => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { message, type: 'error' as ToastType } }));
    }
  },
  warning: (message: string) => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { message, type: 'warning' as ToastType } }));
    }
  },
  info: (message: string) => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail: { message, type: 'info' as ToastType } }));
    }
  },
};
