'use client';

import React, { useId } from 'react';
import { cn } from '@/lib/utils';

export interface BorderBeamProps {
  className?: string;
  active?: boolean;
  durationSec?: number;
  rx?: number;
}

/**
 * Adapted from Magic UI BorderBeam — pure SVG perimeter stroke (`fill="none"`),
 * 100% immune to CSS mask-composite quirks across Chrome/Firefox/Safari and never obscures card content.
 */
export function BorderBeam({
  className,
  active = true,
  durationSec = 7,
  rx = 16,
}: BorderBeamProps) {
  const gradId = useId();
  if (!active) return null;

  return (
    <svg
      aria-hidden
      className={cn('pointer-events-none absolute inset-0 z-20 h-full w-full overflow-visible', className)}
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="rgba(20, 184, 166, 0)" />
          <stop offset="45%" stopColor="rgba(20, 184, 166, 0.9)" />
          <stop offset="75%" stopColor="rgba(94, 234, 212, 1)" />
          <stop offset="100%" stopColor="rgba(20, 184, 166, 0)" />
        </linearGradient>
      </defs>
      <rect
        x="1"
        y="1"
        width="calc(100% - 2px)"
        height="calc(100% - 2px)"
        rx={rx}
        ry={rx}
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="1.75"
        strokeLinecap="round"
        pathLength={100}
        strokeDasharray="24 76"
        className="animate-beam-dash"
        style={{ ['--beam-duration' as string]: `${durationSec}s` }}
      />
    </svg>
  );
}
