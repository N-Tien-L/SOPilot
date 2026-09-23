'use client';

import React from 'react';
import { AlertTriangle, AlertCircle, Info, HelpCircle } from 'lucide-react';
import { Modal } from '../modal';
import { Button } from '../button';
import { clsx } from 'clsx';
import styles from './confirm-dialog.module.css';

type ConfirmVariant = 'danger' | 'warning' | 'info' | 'help';

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
  loading?: boolean;
  hideCancel?: boolean;
  hideConfirm?: boolean;
}

const variantConfig: Record<ConfirmVariant, { icon: React.ReactNode; buttonVariant: 'destructive' | 'secondary' | 'primary' }> = {
  danger: {
    icon: <AlertCircle size={24} />,
    buttonVariant: 'destructive',
  },
  warning: {
    icon: <AlertTriangle size={24} />,
    buttonVariant: 'destructive',
  },
  info: {
    icon: <Info size={24} />,
    buttonVariant: 'primary',
  },
  help: {
    icon: <HelpCircle size={24} />,
    buttonVariant: 'primary',
  },
};

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Hủy',
  variant = 'danger',
  loading = false,
  hideCancel = false,
  hideConfirm = false,
}: ConfirmDialogProps) {
  const config = variantConfig[variant];

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      hideCloseButton
      closeOnOverlayClick={!loading}
      closeOnEscape={!loading}
    >
      <div className={clsx(styles.wrapper, styles[variant])}>
        <div className={styles.iconWrapper}>{config.icon}</div>
        <h2 className={styles.title}>{title}</h2>
        <div className={styles.message}>{message}</div>
        <div className={styles.actions}>
          {!hideCancel && (
            <Button variant="secondary" onClick={onClose} disabled={loading}>
              {cancelLabel}
            </Button>
          )}
          {!hideConfirm && (
            <Button variant={config.buttonVariant} onClick={onConfirm} loading={loading}>
              {confirmLabel}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
