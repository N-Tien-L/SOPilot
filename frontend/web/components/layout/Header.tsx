'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  MessageSquare,
  BookOpen,
  BarChart3,
  Settings,
  User,
  LogOut,
  Menu,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  Shield,
} from 'lucide-react';
import { useAuthStore, useIsManager } from '@/store';
import { useLanguage } from '@/providers';
import { api } from '@/lib/api';
import { UserRole } from '@/types';
import styles from './Header.module.css';

const ROLE_BADGE_CLASS: Record<UserRole, string> = {
  [UserRole.ADMIN]: styles.roleAdmin,
  [UserRole.MANAGER]: styles.roleManager,
  [UserRole.USER]: styles.roleUser,
};

interface HeaderProps {
  onMenuClick: () => void;
  onToggleCollapse?: () => void;
  sidebarCollapsed?: boolean;
}

export default function Header({ onMenuClick, onToggleCollapse, sidebarCollapsed }: HeaderProps) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const { t } = useLanguage();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);
  const isManager = useIsManager();

  // Track store hydration to prevent hydration mismatch
  useEffect(() => {
    const unsubscribe = useAuthStore.subscribe((state) => {
      if (state._hasHydrated) {
        setIsHydrated(true);
      }
    });
    // Check initial state
    if (useAuthStore.getState()._hasHydrated) {
      setIsHydrated(true);
    }
    return unsubscribe;
  }, []);

  const ROLE_LABEL: Record<UserRole, string> = {
    [UserRole.ADMIN]: t('role.admin.short'),
    [UserRole.MANAGER]: t('role.manager.short'),
    [UserRole.USER]: t('role.user.short'),
  };

  const handleLogout = async () => {
    setShowUserMenu(false);
    try {
      await api.auth.logout();
    } catch { /* ignore */ }
    logout();
    window.location.href = '/login';
  };

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <button
          className={`${styles.menuButton} ${styles.desktopOnly}`}
          onClick={onToggleCollapse}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
        </button>
        <button className={`${styles.menuButton} ${styles.mobileOnly}`} onClick={onMenuClick} aria-label="Toggle menu">
          <Menu size={20} />
        </button>

        <Link href="/" className={styles.logo}>
          <div className={styles.logoIcon}>
            <MessageSquare size={24} />
          </div>
          <span className={styles.logoText}>Poliwise</span>
        </Link>
      </div>

      <nav className={styles.nav}>
        <Link
          href="/"
          className={`${styles.navLink} ${pathname === '/' ? styles.active : ''}`}
        >
          <MessageSquare size={18} />
          <span>{t('nav.ask')}</span>
        </Link>

        <Link
          href="/documents"
          className={`${styles.navLink} ${pathname === '/documents' ? styles.active : ''}`}
        >
          <BookOpen size={18} />
          <span>{t('nav.documents')}</span>
        </Link>

        {isHydrated && isManager && (
          <Link
            href="/analytics"
            className={`${styles.navLink} ${pathname === '/analytics' ? styles.active : ''}`}
          >
            <BarChart3 size={18} />
            <span>{t('nav.analytics')}</span>
          </Link>
        )}
      </nav>

      <div className={styles.right}>
        {!isHydrated ? (
          <div className={styles.userButton} style={{ width: 120, height: 36 }} />
        ) : user ? (
          <div className={styles.userMenu}>
            <button
              className={styles.userButton}
              onClick={() => setShowUserMenu(!showUserMenu)}
            >
              <div className={styles.avatar}>
                <User size={16} />
              </div>
              <div className={styles.userInfo}>
                <span className={styles.userName}>{user.username}</span>
                {user.role && (
                  <span className={`${styles.roleBadge} ${ROLE_BADGE_CLASS[user.role]}`}>
                    {ROLE_LABEL[user.role]}
                  </span>
                )}
              </div>
              <ChevronDown size={16} className={styles.chevron} />
            </button>

            {showUserMenu && (
              <div className={styles.dropdown}>
                <Link href="/profile" className={styles.dropdownItem} onClick={() => setShowUserMenu(false)}>
                  <User size={16} />
                  <span>{t('nav.profile')}</span>
                </Link>

                {user.role === UserRole.ADMIN && (
                  <Link href="/admin/settings" className={styles.dropdownItem} onClick={() => setShowUserMenu(false)}>
                    <Settings size={16} />
                    <span>{t('nav.settings')}</span>
                  </Link>
                )}

                {user.role === UserRole.ADMIN && (
                  <Link href="/admin" className={styles.dropdownItem} onClick={() => setShowUserMenu(false)}>
                    <Shield size={16} />
                    <span>{t('nav.admin')}</span>
                  </Link>
                )}

                <div className={styles.divider} />

                <button onClick={handleLogout} className={styles.dropdownItem}>
                  <LogOut size={16} />
                  <span>{t('nav.logout')}</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link href="/login" className={styles.loginButton}>
            {t('nav.login')}
          </Link>
        )}
      </div>
    </header>
  );
}
