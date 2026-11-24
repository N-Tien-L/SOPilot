'use client';

import React from 'react';
import { SpotlightCard } from '@/components/effects';
import { cn } from '@/lib/utils';

export interface StatCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  className?: string;
}

export function StatCard({ label, value, hint, icon, className }: StatCardProps) {
  return (
    <SpotlightCard className={cn('p-4', className)}>
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span>{label}</span>
        {icon ? (
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-foreground">{value}</div>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </SpotlightCard>
  );
}

export default StatCard;
