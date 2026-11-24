'use client';

import React, { useEffect, useRef } from 'react';
import { useMotionValue, useSpring } from 'motion/react';
import { cn } from '@/lib/utils';

export interface CountUpProps {
  to: number;
  from?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}

/**
 * Adapted from React Bits CountUp — smooth spring-eased counter updating textContent directly
 * (zero per-frame React re-renders, respects prefers-reduced-motion).
 */
export function CountUp({
  to,
  from = 0,
  decimals = 0,
  suffix = '',
  prefix = '',
  className,
}: CountUpProps) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const mv = useMotionValue(from);
  const spring = useSpring(mv, { stiffness: 90, damping: 20, mass: 0.8 });

  useEffect(() => {
    const format = (v: number) => `${prefix}${v.toFixed(decimals)}${suffix}`;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      mv.jump(to);
      if (spanRef.current) spanRef.current.textContent = format(to);
      return;
    }
    const unsub = spring.on('change', (latest) => {
      if (spanRef.current) spanRef.current.textContent = format(latest);
    });
    mv.set(to);
    return () => unsub();
  }, [to, decimals, prefix, suffix, mv, spring]);

  return (
    <span ref={spanRef} className={cn('tabular-nums', className)}>
      {prefix}
      {from.toFixed(decimals)}
      {suffix}
    </span>
  );
}
