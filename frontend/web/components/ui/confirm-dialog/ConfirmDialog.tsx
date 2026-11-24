'use client';

import React from 'react';
import { AlertCircle, AlertTriangle, HelpCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '../button';
import { Modal } from '../modal';

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

const variantConfig: Record<
  ConfirmVariant,
  { icon: React.ReactNode; tone: string; buttonVariant: 'destructive' | 'secondary' | 'primary' }
> = {
  danger: {
    icon: <AlertCircle size={22} aria-hidden />,
    tone: 'bg-danger-soft text-danger-foreground',
    buttonVariant: 'destructive',
  },
  warning: {
    icon: <AlertTriangle size={22} aria-hidden />,
    tone: 'bg-warning-soft text-warning-foreground',
    buttonVariant: 'destructive',
  },
  info: {
    icon: <Info size={22} aria-hidden />,
    tone: 'bg-info-soft text-info-foreground',
    buttonVariant: 'primary',
  },
  help: {
    icon: <HelpCircle size={22} aria-hidden />,
    tone: 'bg-primary-soft text-primary-strong',
    buttonVariant: 'primary',
  },
};

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
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
      <div className="flex flex-col items-center text-center">
        <div
          className={cn(
            'flex h-12 w-12 items-center justify-center rounded-2xl',
            config.tone,
          )}
        >
          {config.icon}
        </div>
        <h2 className="mt-4 text-lg font-bold tracking-tight text-foreground">{title}</h2>
        <div className="mt-2 text-sm leading-relaxed text-muted-foreground">{message}</div>
        <div className="mt-6 flex w-full justify-end gap-2">
          {!hideCancel ? (
            <Button variant="outline" onClick={onClose} disabled={loading}>
              {cancelLabel}
            </Button>
          ) : null}
          {!hideConfirm ? (
            <Button variant={config.buttonVariant} onClick={onConfirm} loading={loading}>
              {confirmLabel}
            </Button>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
