'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import styles from './spinner.module.css';

type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg';

export interface SpinnerProps {
  size?: SpinnerSize;
  className?: string;
  label?: string;
}

const sizeMap: Record<SpinnerSize, number> = {
  xs: 12,
  sm: 16,
  md: 24,
  lg: 32,
};

export function Spinner({ size = 'md', className, label }: SpinnerProps) {
  return (
    <div className={clsx(styles.wrapper, className)} role="status" aria-label={label || 'Loading'}>
      <Loader2 size={sizeMap[size]} className={styles.spinner} />
      {label && <span className={styles.label}>{label}</span>}
    </div>
  );
}

export default Spinner;
