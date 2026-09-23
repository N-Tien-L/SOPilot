'use client';

import React, { createContext, useState } from 'react';
import { clsx } from 'clsx';
import styles from './tabs.module.css';

interface TabItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  content: React.ReactNode;
}

interface TabsContextValue {
  activeTab: string;
  setActiveTab: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

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
  variant = 'default',
}: TabsProps) {
  const [internalValue, setInternalValue] = useState(defaultValue || tabs[0]?.value);
  const activeTab = value ?? internalValue;

  const handleTabChange = (tabValue: string) => {
    if (value === undefined) {
      setInternalValue(tabValue);
    }
    onChange?.(tabValue);
  };

  const activeContent = tabs.find((t) => t.value === activeTab)?.content;

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab: handleTabChange }}>
      <div className={clsx(styles.tabs, styles[variant], className)}>
        <div className={styles.tabList} role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              role="tab"
              type="button"
              disabled={tab.disabled}
              aria-selected={activeTab === tab.value}
              className={clsx(styles.tab, activeTab === tab.value && styles.active)}
              onClick={() => handleTabChange(tab.value)}
            >
              {tab.icon && <span className={styles.icon}>{tab.icon}</span>}
              {tab.label}
            </button>
          ))}
        </div>
        <div className={styles.content} role="tabpanel">
          {activeContent}
        </div>
      </div>
    </TabsContext.Provider>
  );
}

export default Tabs;
