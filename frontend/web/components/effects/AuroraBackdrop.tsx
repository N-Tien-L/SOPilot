'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface AuroraBackdropProps {
  className?: string;
  /** 'ink' is tailored for dark hero panels (e.g. Login left rail); 'subtle' for light/dark canvas tint. */
  variant?: 'ink' | 'subtle';
}

/**
 * Adapted from React Bits Aurora — pure CSS GPU-composited mesh backdrop
 * (zero WebGL dependency, zero headless-browser context errors, pauses under reduced motion).
 */
export function AuroraBackdrop({ className, variant = 'ink' }: AuroraBackdropProps) {
  if (variant === 'subtle') {
    return (
      <div aria-hidden className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}>
        <div
          className="animate-aurora-a absolute -left-24 -top-24 h-80 w-80 rounded-full opacity-25 blur-3xl dark:opacity-20"
          style={{
            background:
              'radial-gradient(circle, rgba(20,184,166,0.55) 0%, rgba(15,118,110,0.18) 55%, transparent 75%)',
          }}
        />
        <div
          className="animate-aurora-b absolute -bottom-24 -right-24 h-96 w-96 rounded-full opacity-20 blur-3xl dark:opacity-15"
          style={{
            background:
              'radial-gradient(circle, rgba(56,189,248,0.4) 0%, rgba(15,118,110,0.15) 55%, transparent 75%)',
          }}
        />
      </div>
    );
  }

  return (
    <div aria-hidden className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}>
      <div
        className="animate-aurora-a absolute -left-[18%] -top-[20%] h-[68%] w-[78%] rounded-full opacity-55 blur-[88px]"
        style={{
          background:
            'radial-gradient(circle at 40% 40%, rgba(20, 184, 166, 0.65) 0%, rgba(15, 118, 110, 0.25) 48%, transparent 72%)',
        }}
      />
      <div
        className="animate-aurora-b absolute -bottom-[24%] -right-[16%] h-[72%] w-[76%] rounded-full opacity-45 blur-[96px]"
        style={{
          background:
            'radial-gradient(circle at 60% 60%, rgba(45, 212, 191, 0.45) 0%, rgba(14, 116, 144, 0.28) 50%, transparent 74%)',
        }}
      />
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            'radial-gradient(rgba(94, 234, 212, 0.22) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
          maskImage: 'radial-gradient(ellipse 75% 70% at 50% 45%, black 20%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(ellipse 75% 70% at 50% 45%, black 20%, transparent 80%)',
        }}
      />
    </div>
  );
}
