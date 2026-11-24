'use client';

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold leading-5 whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'bg-primary-soft text-primary-strong',
        success: 'bg-success-soft text-success-foreground',
        warning: 'bg-warning-soft text-warning-foreground',
        destructive: 'bg-danger-soft text-danger-foreground',
        danger: 'bg-danger-soft text-danger-foreground',
        info: 'bg-info-soft text-info-foreground',
        neutral: 'border border-border bg-muted text-muted-foreground',
        purple: 'bg-purple-soft text-purple-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export interface BadgeProps extends VariantProps<typeof badgeVariants> {
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export function Badge({ variant = 'default', children, className, icon }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)}>
      {icon ? <span className="inline-flex shrink-0 items-center">{icon}</span> : null}
      {children}
    </span>
  );
}

export default Badge;
