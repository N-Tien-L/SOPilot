'use client';

import { useId } from 'react';
import { motion } from 'motion/react';

export interface TabItem<T extends string> {
  id: T;
  label: string;
}

/**
 * WAI-ARIA tabs: arrows move between tabs (wrapping), Home and End jump to the ends. The caller
 * renders the panel with `id={`panel-${current}`}` and `aria-labelledby={`tab-${current}`}`.
 */
export function TabList<T extends string>({
  label,
  tabs,
  current,
  onSelect,
}: {
  label: string;
  tabs: readonly TabItem<T>[];
  current: T;
  onSelect: (id: T) => void;
}) {
  const layoutId = useId();

  return (
    <div role="tablist" aria-label={label} className="mt-4 flex flex-wrap gap-1 border-b border-border">
      {tabs.map((t) => {
        const active = current === t.id;
        return (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={active}
            aria-controls={`panel-${t.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(t.id)}
            onKeyDown={(e) => {
              const i = tabs.findIndex((x) => x.id === t.id);
              const next =
                e.key === 'ArrowRight' ? (i + 1) % tabs.length
                : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length
                : e.key === 'Home' ? 0
                : e.key === 'End' ? tabs.length - 1
                : -1;
              if (next < 0) return;
              e.preventDefault();
              onSelect(tabs[next].id);
              document.getElementById(`tab-${tabs[next].id}`)?.focus();
            }}
            className={`relative cursor-pointer px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
              active ? 'font-semibold text-primary-strong' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
            {active ? (
              <motion.span
                layoutId={`tablist-${layoutId}`}
                className="absolute inset-x-1 -bottom-px h-0.5 rounded-full bg-primary"
                transition={{ type: 'spring', stiffness: 460, damping: 34 }}
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
