'use client';

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { clsx } from 'clsx';
import styles from './stat-card.module.css';

type TrendDirection = 'up' | 'down' | 'neutral';
type StatTone = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'purple';

export interface StatCardProps {
  label: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  trend?: TrendDirection;
  tone?: StatTone;
  meta?: React.ReactNode;
  status?: React.ReactNode;
  className?: string;
}

export function StatCard({
  label,
  value,
  change,
  changeLabel,
  icon,
  trend,
  tone = 'default',
  meta,
  status,
  className,
}: StatCardProps) {
  const resolvedTrend = trend || (change !== undefined ? (change > 0 ? 'up' : change < 0 ? 'down' : 'neutral') : 'neutral');

  return (
    <div className={clsx(styles.card, styles[tone], className)}>
      <div className={styles.header}>
        <span className={styles.label}>{label}</span>
        {icon && <div className={styles.icon}>{icon}</div>}
      </div>
      <div className={styles.body}>
        <span className={styles.value}>{value}</span>
        {change !== undefined && (
          <div className={clsx(styles.change, styles[resolvedTrend])}>
            {resolvedTrend === 'up' && <TrendingUp size={14} />}
            {resolvedTrend === 'down' && <TrendingDown size={14} />}
            {resolvedTrend === 'neutral' && <Minus size={14} />}
            <span>
              {change > 0 ? '+' : ''}
              {change}
              {changeLabel && ` ${changeLabel}`}
            </span>
          </div>
        )}
      </div>
      {(meta || status) && (
        <div className={styles.footer}>
          {meta && <span className={styles.meta}>{meta}</span>}
          {status && <span className={styles.status}>{status}</span>}
        </div>
      )}
    </div>
  );
}

export default StatCard;
