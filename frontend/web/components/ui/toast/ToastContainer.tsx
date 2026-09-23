'use client';

import React from 'react';
import { useToast, ToastType } from './ToastContext';

const iconMap: Record<ToastType, string> = {
  error: '✕',
  success: '✓',
  warning: '⚠',
  info: 'ℹ',
};

export function ToastContainer() {
  const { toasts, removeToast, addToast } = useToast();

  React.useEffect(() => {
    const handleToast = (e: Event) => {
      const custom = e as CustomEvent<{ message: string; type: ToastType }>;
      addToast(custom.detail.message, custom.detail.type);
    };
    window.addEventListener('poliwise-toast', handleToast);
    return () => window.removeEventListener('poliwise-toast', handleToast);
  }, [addToast]);

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 400,
      }}
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          onClick={() => removeToast(toast.id)}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            padding: '12px 16px',
            borderRadius: 8,
            background: '#fff',
            boxShadow: '0 4px 16px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.08)',
            borderLeft: `4px solid ${
              toast.type === 'error'
                ? '#ef4444'
                : toast.type === 'success'
                ? '#22c55e'
                : toast.type === 'warning'
                ? '#f59e0b'
                : '#3b82f6'
            }`,
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1.5,
            color: '#1f2937',
            animation: 'slideIn 0.2s ease-out',
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              fontWeight: 700,
              flexShrink: 0,
              background:
                toast.type === 'error'
                  ? '#fef2f2'
                  : toast.type === 'success'
                  ? '#f0fdf4'
                  : toast.type === 'warning'
                  ? '#fffbeb'
                  : '#eff6ff',
              color:
                toast.type === 'error'
                  ? '#dc2626'
                  : toast.type === 'success'
                  ? '#16a34a'
                  : toast.type === 'warning'
                  ? '#d97706'
                  : '#2563eb',
            }}
          >
            {iconMap[toast.type]}
          </span>
          <span style={{ flex: 1 }}>{toast.message}</span>
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
