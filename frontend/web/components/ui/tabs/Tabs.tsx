'use client';

import React, { useId, useState } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

interface TabItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  content: React.ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
  variant?: 'default' | 'pills' | 'underline';
}

export function Tabs({
  tabs,
  defaultValue,
  value,
  onChange,
  className,
  variant = 'underline',
}: TabsProps) {
  const layoutId = useId();
  const [internalValue, setInternalValue] = useState(defaultValue || tabs[0]?.value);
  const activeTab = value ?? internalValue;

  const handleTabChange = (tabValue: string) => {
    if (value === undefined) setInternalValue(tabValue);
    onChange?.(tabValue);
  };

  const activeContent = tabs.find((t) => t.value === activeTab)?.content;

  return (
    <div className={cn('space-y-4', className)}>
      <div
        role="tablist"
        className={cn(
          'flex flex-wrap gap-1',
          variant === 'pills'
            ? 'inline-flex rounded-xl border border-border bg-muted p-1'
            : 'border-b border-border',
        )}
      >
        {tabs.map((tab) => {
          const active = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              role="tab"
              type="button"
              disabled={tab.disabled}
              aria-selected={active}
              onClick={() => handleTabChange(tab.value)}
              className={cn(
                'relative inline-flex cursor-pointer items-center gap-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-45',
                variant === 'pills'
                  ? cn('rounded-lg px-3 py-1.5', active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')
                  : cn('px-4 py-2.5', active ? 'text-primary-strong font-semibold' : 'text-muted-foreground hover:text-foreground'),
              )}
            >
              {active && variant === 'pills' ? (
                <motion.span
                  layoutId={`tabs-${layoutId}`}
                  className="absolute inset-0 rounded-lg bg-card shadow-xs"
                  transition={{ type: 'spring', stiffness: 450, damping: 34 }}
                />
              ) : null}
              <span className="relative z-10 inline-flex items-center gap-1.5">
                {tab.icon ? <span aria-hidden>{tab.icon}</span> : null}
                {tab.label}
              </span>
              {active && variant !== 'pills' ? (
                <motion.span
                  layoutId={`tabs-${layoutId}`}
                  className="absolute inset-x-1 -bottom-px h-0.5 rounded-full bg-primary"
                  transition={{ type: 'spring', stiffness: 460, damping: 34 }}
                />
              ) : null}
            </button>
          );
        })}
      </div>
      <div role="tabpanel">{activeContent}</div>
    </div>
  );
}

export default Tabs;
