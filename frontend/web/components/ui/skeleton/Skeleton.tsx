'use client';

import React from 'react';
import { cn } from '@/lib/utils';

type SkeletonVariant = 'text' | 'circular' | 'rectangular';
type SkeletonSize = 'sm' | 'md' | 'lg';

export interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  size?: SkeletonSize;
  className?: string;
  count?: number;
}

const SIZE_HEIGHT: Record<SkeletonSize, string> = {
  sm: '0.75rem',
  md: '1rem',
  lg: '1.5rem',
};

export function Skeleton({
  variant = 'text',
  width,
  height,
  size = 'md',
  className,
  count = 1,
}: SkeletonProps) {
  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;
  else if (variant === 'text') style.height = SIZE_HEIGHT[size];

  const radius =
    variant === 'circular' ? 'rounded-full' : variant === 'rectangular' ? 'rounded-xl' : 'rounded-lg';

  const elements = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      aria-hidden
      className={cn('animate-shimmer w-full', radius, count > 1 && i > 0 && 'mt-2.5', className)}
      style={style}
    />
  ));

  if (count === 1) return elements[0];
  return <div>{elements}</div>;
}

export default Skeleton;
