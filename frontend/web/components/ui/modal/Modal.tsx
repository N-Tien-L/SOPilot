'use client';

import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'motion/react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'full';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  size?: ModalSize;
  children: React.ReactNode;
  footer?: React.ReactNode;
  hideCloseButton?: boolean;
  closeOnOverlayClick?: boolean;
  closeOnEscape?: boolean;
  className?: string;
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: 'w-[min(92vw,26rem)]',
  md: 'w-[min(92vw,32rem)]',
  lg: 'w-[min(92vw,42rem)]',
  xl: 'w-[min(94vw,60rem)]',
  full: 'w-[min(96vw,78rem)]',
};

export function Modal({
  open,
  onClose,
  title,
  description,
  size = 'md',
  children,
  footer,
  hideCloseButton = false,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  className,
}: ModalProps) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.16 }}
                className="fixed inset-0 z-50 bg-overlay backdrop-blur-xs"
              />
            </Dialog.Overlay>
            <Dialog.Content
              asChild
              onPointerDownOutside={(e) => {
                if (!closeOnOverlayClick) e.preventDefault();
              }}
              onInteractOutside={(e) => {
                if (!closeOnOverlayClick) e.preventDefault();
              }}
              onEscapeKeyDown={(e) => {
                if (!closeOnEscape) e.preventDefault();
              }}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96, y: 8 }}
                transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                className={cn(
                  'fixed left-1/2 top-1/2 z-50 flex max-h-[88dvh] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-border bg-card-elevated text-card-foreground shadow-[var(--shadow-lg)] focus:outline-none',
                  SIZE_CLASSES[size],
                  className,
                )}
              >
                {title || description || !hideCloseButton ? (
                  <div className="flex items-start justify-between gap-4 border-b border-border/80 px-6 py-4">
                    <div className="min-w-0">
                      {title ? (
                        <Dialog.Title className="text-lg font-bold tracking-tight text-foreground">
                          {title}
                        </Dialog.Title>
                      ) : (
                        <Dialog.Title className="sr-only">Dialog</Dialog.Title>
                      )}
                      {description ? (
                        <Dialog.Description className="mt-1 text-xs leading-relaxed text-muted-foreground">
                          {description}
                        </Dialog.Description>
                      ) : null}
                    </div>
                    {!hideCloseButton ? (
                      <Dialog.Close asChild>
                        <button
                          type="button"
                          aria-label="Close modal"
                          data-modal-close
                          className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                        >
                          <X size={18} aria-hidden />
                        </button>
                      </Dialog.Close>
                    ) : null}
                  </div>
                ) : (
                  <Dialog.Title className="sr-only">Dialog</Dialog.Title>
                )}

                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>

                {footer ? (
                  <div className="border-t border-border/80 bg-muted/35 px-6 py-3.5">{footer}</div>
                ) : null}
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}

export default Modal;
