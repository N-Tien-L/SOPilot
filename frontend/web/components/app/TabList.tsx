'use client';

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
  return (
    <div role="tablist" aria-label={label} className="mt-4 flex flex-wrap gap-1 border-b border-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          id={`tab-${t.id}`}
          role="tab"
          type="button"
          aria-selected={current === t.id}
          aria-controls={`panel-${t.id}`}
          tabIndex={current === t.id ? 0 : -1}
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
          className={`px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring ${
            current === t.id ? 'border-b-2 border-primary font-semibold text-primary-strong' : 'text-muted-foreground'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
