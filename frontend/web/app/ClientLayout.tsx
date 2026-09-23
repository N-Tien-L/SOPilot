'use client';

import React from 'react';
import { ToastProvider } from '@/components/ui/toast/ToastProvider';

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      {children}
    </ToastProvider>
  );
}
