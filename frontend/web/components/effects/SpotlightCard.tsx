'use client';

import React, { useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  spotlightColor?: string;
  overlay?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Adapted from React Bits SpotlightCard — subtle mouse-tracking radial teal highlight
 * on an elevated card surface.
 */
export function SpotlightCard({
  children,
  className,
  spotlightColor = 'rgba(20, 184, 166, 0.14)',
  overlay,
  onMouseMove,
  onMouseEnter,
  onMouseLeave,
  ...props
}: SpotlightCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  return (
    <div
      ref={ref}
      onMouseMove={(e) => {
        if (ref.current) {
          const rect = ref.current.getBoundingClientRect();
          setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        }
        onMouseMove?.(e);
      }}
      onMouseEnter={(e) => {
        setOpacity(1);
        onMouseEnter?.(e);
      }}
      onMouseLeave={(e) => {
        setOpacity(0);
        onMouseLeave?.(e);
      }}
      className={cn(
        'relative overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-sm)] transition-[border-color,box-shadow] duration-200 hover:border-primary/40 hover:shadow-[var(--shadow-md)]',
        className,
      )}
      {...props}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(360px circle at ${pos.x}px ${pos.y}px, ${spotlightColor}, transparent 70%)`,
        }}
      />
      {overlay}
      <div className="relative z-10">{children}</div>
    </div>
  );
}
