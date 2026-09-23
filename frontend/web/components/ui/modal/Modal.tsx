'use client';

import React, { useEffect, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { clsx } from 'clsx';
import styles from './modal.module.css';

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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (closeOnEscape && e.key === 'Escape') {
        onClose();
      }
    },
    [closeOnEscape, onClose]
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, handleKeyDown]);

  if (!open || !mounted) return null;

  const modalContent = (
    <div className={styles.overlay} onClick={closeOnOverlayClick ? onClose : undefined}>
      <div
        className={clsx(styles.modal, styles[size], className)}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'modal-title' : undefined}
        aria-describedby={description ? 'modal-description' : undefined}
      >
        {(title || !hideCloseButton) && (
          <div className={styles.header}>
            <div className={styles.headerContent}>
              {title && (
                <h2 id="modal-title" className={styles.title}>
                  {title}
                </h2>
              )}
              {description && (
                <p id="modal-description" className={styles.description}>
                  {description}
                </p>
              )}
            </div>
            {!hideCloseButton && (
              <button
                type="button"
                className={styles.closeButton}
                onClick={onClose}
                aria-label="Close modal"
              >
                <X size={20} />
              </button>
            )}
          </div>
        )}
        <div className={styles.content}>{children}</div>
        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}

export default Modal;
