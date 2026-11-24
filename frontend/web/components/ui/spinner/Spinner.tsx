'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_PX = { sm: 14, md: 20, lg: 28 };

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <Loader2
      size={SIZE_PX[size]}
      aria-label="Loading"
      className={cn('animate-spin text-primary', className)}
    />
  );
}

export default Spinner;
