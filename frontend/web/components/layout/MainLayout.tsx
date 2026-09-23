'use client';

import { useEffect, useState } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('sidebar-collapsed') : null;
    if (saved === 'true') setSidebarCollapsed(true);
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarCollapsed(true);
        setSidebarOpen(false);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebarCollapse = () => {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sidebar-collapsed', String(next));
    }
  };

  return (
    <div className={styles.layout} data-sidebar-open={sidebarOpen} data-sidebar-collapsed={sidebarCollapsed}>
      <Header
        onMenuClick={() => setSidebarOpen(!sidebarOpen)}
        onToggleCollapse={toggleSidebarCollapse}
        sidebarCollapsed={sidebarCollapsed}
      />
      <Sidebar
        isOpen={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
      />

      <main className={styles.main}>
        <div className={styles.content}>
          {children}
        </div>
      </main>
    </div>
  );
}
