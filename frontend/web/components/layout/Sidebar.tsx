'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  MessageSquare,
  BookOpen,
  BarChart3,
  Users,
  Tags,
  FolderOpen,
  Shield,
  FileBarChart,
  ScrollText,
  Brain,
  Settings,
  User,
  X,
  LogOut,
  Building2,
  ShieldAlert,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useUserRole, useAuthStore } from '@/store';
import { useLanguage } from '@/providers';
import { UserRole } from '@/types';
import styles from './Sidebar.module.css';

interface SidebarProps {
  isOpen: boolean;
  collapsed: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, collapsed, onClose }: SidebarProps) {
  const pathname = usePathname();
  const userRole = useUserRole();
  const { t } = useLanguage();

  const filterByRole = (items: { label: string; href: string; icon: React.ReactNode; roles?: UserRole[]; dividerBefore?: boolean }[]) =>
    items.filter((item) => !item.roles || item.roles.includes(userRole as UserRole));

  const NAV_ITEMS = [
    { label: t('nav.ask'), href: '/', icon: <MessageSquare size={20} /> },
    { label: t('nav.documents'), href: '/documents', icon: <BookOpen size={20} /> },
    { label: t('nav.analytics'), href: '/analytics', icon: <BarChart3 size={20} />, roles: [UserRole.MANAGER, UserRole.ADMIN] as UserRole[] },
  ];

  const ADMIN_ITEMS = [
    { label: t('admin.users.title'), href: '/admin/users', icon: <Users size={20} />, roles: [UserRole.ADMIN] as UserRole[], dividerBefore: true },
    { label: t('admin.depts.title'), href: '/admin/departments', icon: <Building2 size={20} />, roles: [UserRole.ADMIN] as UserRole[] },
    { label: t('admin.categories.title'), href: '/admin/metadata/categories', icon: <FolderOpen size={20} />, roles: [UserRole.ADMIN] as UserRole[] },
    { label: t('admin.tags.title'), href: '/admin/metadata/tags', icon: <Tags size={20} />, roles: [UserRole.ADMIN] as UserRole[] },
    { label: t('admin.audit.title'), href: '/admin/audit-logs', icon: <ScrollText size={20} />, roles: [UserRole.ADMIN] as UserRole[], dividerBefore: true },
    { label: t('admin.unanswered.title'), href: '/admin/unanswered', icon: <Brain size={20} />, roles: [UserRole.ADMIN, UserRole.MANAGER] as UserRole[], dividerBefore: true },
    { label: t('analytics.export'), href: '/analytics/reports', icon: <FileBarChart size={20} />, roles: [UserRole.ADMIN, UserRole.MANAGER] as UserRole[] },
  ];

  const filteredNav = filterByRole(NAV_ITEMS);
  const filteredAdmin = filterByRole(ADMIN_ITEMS);

  const handleLogout = () => {
    useAuthStore.getState().logout();
    onClose();
    window.location.href = '/login';
  };

  const renderNavItem = (item: { label: string; href: string; icon: React.ReactNode; roles?: UserRole[]; dividerBefore?: boolean }) => (
    <Link
      key={item.href}
      href={item.href}
      className={clsx(styles.navItem, pathname === item.href && styles.active)}
      onClick={onClose}
      title={collapsed ? item.label : undefined}
    >
      {item.icon}
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );

  return (
    <>
      {isOpen && (
        <div
          className={styles.overlay}
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={clsx(styles.sidebar, isOpen && styles.open, collapsed && styles.collapsed)}>
        <div className={styles.header}>
          <span className={styles.title}>Menu</span>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close sidebar">
            <X size={20} />
          </button>
        </div>

        <nav className={styles.nav}>
          <div className={styles.section}>
            {filteredNav.map(renderNavItem)}
          </div>

          {filteredAdmin.length > 0 && (
            <div className={styles.section}>
              {!collapsed && (
                <span className={styles.sectionTitle}>
                  <Shield size={14} />
                  {t('nav.admin')}
                </span>
              )}
              {filteredAdmin.map((item) => (
                <div key={item.href}>
                  {item.dividerBefore && <div className={styles.divider} />}
                  {renderNavItem(item)}
                </div>
              ))}
            </div>
          )}
        </nav>

        <div className={styles.footer}>
          <Link href="/profile" className={styles.navItem} onClick={onClose} title={collapsed ? t('nav.profile') : undefined}>
            <User size={20} />
            {!collapsed && <span>{t('nav.profile')}</span>}
          </Link>
          <Link href="/admin/settings" className={styles.navItem} onClick={onClose} title={collapsed ? t('nav.settings') : undefined}>
            <Settings size={20} />
            {!collapsed && <span>{t('nav.settings')}</span>}
          </Link>
          <button className={styles.navItem} onClick={handleLogout} title={collapsed ? t('nav.logout') : undefined}>
            <LogOut size={20} />
            {!collapsed && <span>{t('nav.logout')}</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
