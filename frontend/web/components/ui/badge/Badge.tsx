'use client';

import React from 'react';
import { clsx } from 'clsx';
import styles from './badge.module.css';

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'danger' | 'info' | 'neutral' | 'purple';

export interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export function Badge({ variant = 'default', children, className, icon }: BadgeProps) {
  return (
    <span className={clsx(styles.badge, styles[variant], className)}>
      {icon && <span className={styles.icon}>{icon}</span>}
      {children}
    </span>
  );
}

export default Badge;
