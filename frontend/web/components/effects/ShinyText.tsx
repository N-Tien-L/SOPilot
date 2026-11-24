'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface ShinyTextProps {
  children: React.ReactNode;
  className?: string;
  active?: boolean;
}

/**
 * Adapted from React Bits ShinyText — crisp light sweep across status text
 * (e.g., "Thinking…", "Searching your documents…", "Processing").
 */
export function ShinyText({ children, className, active = true }: ShinyTextProps) {
  if (!active) {
    return <span className={className}>{children}</span>;
  }

  return (
    <span
      className={cn(
        'animate-shiny-text inline-block bg-clip-text text-transparent',
        'bg-[linear-gradient(110deg,var(--muted-foreground)_35%,var(--primary-strong)_50%,var(--muted-foreground)_65%)]',
        className,
      )}
    >
      {children}
    </span>
  );
}
