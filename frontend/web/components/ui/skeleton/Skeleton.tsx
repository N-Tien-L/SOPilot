'use client';

import React from 'react';
import { clsx } from 'clsx';
import styles from './skeleton.module.css';

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

  const sizeMap: Record<SkeletonSize, React.CSSProperties> = {
    sm: { height: '0.75rem' },
    md: { height: '1rem' },
    lg: { height: '1.5rem' },
  };

  const variantClasses: Record<SkeletonVariant, string> = {
    text: styles.text,
    circular: styles.circular,
    rectangular: styles.rectangular,
  };

  const elements = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      className={clsx(styles.skeleton, variantClasses[variant], className)}
      style={{ ...(variant === 'text' ? sizeMap[size] : {}), ...style }}
    />
  ));

  if (count === 1) return elements[0];
  return <>{elements}</>;
}

export default Skeleton;
