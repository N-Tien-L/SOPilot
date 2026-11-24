'use client';

import React from 'react';
import { ThemeProvider as NextThemesProvider, useTheme } from 'next-themes';
import { MotionConfig } from 'motion/react';
import { Toaster } from 'sonner';

function ThemeToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            'font-sans !rounded-xl !border !border-border !bg-card-elevated !text-foreground !shadow-lg',
          description: '!text-muted-foreground',
        },
      }}
    />
  );
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      storageKey="sopilot-theme"
      disableTransitionOnChange
    >
      <MotionConfig reducedMotion="user" transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
        {children}
        <ThemeToaster />
      </MotionConfig>
    </NextThemesProvider>
  );
}
