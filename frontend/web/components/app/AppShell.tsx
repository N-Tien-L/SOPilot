'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import {
  Building2,
  FileText,
  Flag,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Settings,
  Users,
  WifiOff,
  X,
} from 'lucide-react';
import { Avatar, Button, Spinner } from '@/components/ui';
import { BrandMark } from '@/components/motion/Primitives';
import { ConversationList } from '@/components/chat/ConversationList';
import { showDepartments } from '@/lib/admin/members';
import { restoreSession, signOut } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { useSessionStore } from '@/store/session-store';
import { CommandMenu } from './CommandMenu';
import { ThemeToggle } from './ThemeToggle';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  /** Roles that see the item; the server stays the authority (C7). */
  roles?: readonly string[];
  /** Hidden in a personal workspace, which has no departments. */
  teamOnly?: boolean;
}

const NAV: NavItem[] = [
  { href: '/chat', label: 'Chat', icon: <MessageSquare size={16} aria-hidden /> },
  { href: '/documents', label: 'Documents', icon: <FileText size={16} aria-hidden /> },
  { href: '/members', label: 'Members', icon: <Users size={16} aria-hidden />, roles: ['OWNER', 'ADMIN'] },
  { href: '/departments', label: 'Departments', icon: <Building2 size={16} aria-hidden />, roles: ['OWNER', 'ADMIN'], teamOnly: true },
  { href: '/gaps', label: 'Knowledge gaps', icon: <Flag size={16} aria-hidden />, roles: ['OWNER', 'ADMIN'] },
  { href: '/audit', label: 'Audit log', icon: <ScrollText size={16} aria-hidden />, roles: ['OWNER'] },
  { href: '/settings', label: 'Settings', icon: <Settings size={16} aria-hidden /> },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const status = useSessionStore((s) => s.status);
  const user = useSessionStore((s) => s.user);
  const workspace = useSessionStore((s) => s.workspace);
  const pendingInvites = useSessionStore((s) => s.pendingInvitations.length);
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (status === 'anonymous') router.replace('/login');
  }, [status, router]);

  if (status === 'unreachable') {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-background p-6">
        <div className="max-w-md rounded-2xl border border-border bg-card p-6 text-center shadow-[var(--shadow-md)]">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-warning-soft text-warning-foreground">
            <WifiOff size={22} aria-hidden />
          </span>
          <h1 className="mt-4 text-lg font-bold text-foreground">Connection interrupted</h1>
          <p role="alert" className="mt-1.5 text-sm text-muted-foreground">
            The server could not be reached. Your session is kept; try again.
          </p>
          <div className="mt-5">
            <Button variant="primary" onClick={() => void restoreSession()}>
              Retry
            </Button>
          </div>
        </div>
      </main>
    );
  }
  if (status !== 'authenticated' || !user || !workspace) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-3 bg-background p-8 text-sm text-muted-foreground">
        <BrandMark className="h-10 w-10" />
        <div className="flex items-center gap-2">
          <Spinner size="sm" />
          <span>Loading workspace…</span>
        </div>
      </main>
    );
  }

  const items = NAV.filter(
    (n) => (!n.roles || n.roles.includes(workspace.role)) && !(n.teamOnly && !showDepartments(workspace.kind)),
  );

  const renderNav = (compact: boolean) => (
    <nav
      aria-label="Main"
      className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-2.5 pb-4 pt-1"
      onClick={(e) => {
        if ((e.target as HTMLElement).closest('a')) setDrawer(false);
      }}
    >
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? 'page' : undefined}
            title={compact ? item.label : undefined}
            className={`relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring ${
              active
                ? 'text-sidebar-foreground'
                : 'text-sidebar-muted hover:bg-white/[0.06] hover:text-sidebar-foreground'
            }`}
          >
            {active ? (
              <motion.span
                layoutId={compact ? 'sidebar-active-compact' : 'sidebar-active'}
                className="absolute inset-0 rounded-xl bg-teal-500/18 ring-1 ring-inset ring-teal-400/25"
                transition={{ type: 'spring', stiffness: 420, damping: 32 }}
              />
            ) : null}
            <span className={`relative z-10 shrink-0 ${active ? 'text-sidebar-accent' : ''}`}>
              {item.icon}
            </span>
            {!compact ? <span className="relative z-10 truncate">{item.label}</span> : null}
          </Link>
        );
      })}
      {!compact ? (
        <>
          <div className="my-3 border-t border-white/10" />
          <ConversationList />
        </>
      ) : null}
    </nav>
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background md:flex-row">
      {/* Desktop Deep Ink Sidebar */}
      <aside
        className={`sidebar-ink-bg hidden shrink-0 flex-col border-r border-white/10 text-sidebar-foreground transition-[width] duration-200 md:flex ${
          collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        <div
          className={
            collapsed
              ? 'flex flex-col items-center gap-2 px-2 py-3'
              : 'flex h-[60px] items-center justify-between px-4'
          }
        >
          <Link href="/chat" className="flex min-w-0 items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-ring">
            <BrandMark className="h-7 w-7" />
            {!collapsed ? (
              <span className="truncate text-base font-bold tracking-tight text-sidebar-foreground">SOPilot</span>
            ) : null}
          </Link>
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="cursor-pointer rounded-lg p-1.5 text-sidebar-muted transition-colors hover:bg-white/10 hover:text-sidebar-foreground focus-visible:outline-2 focus-visible:outline-ring"
          >
            {collapsed ? <PanelLeftOpen size={15} aria-hidden /> : <PanelLeftClose size={15} aria-hidden />}
          </button>
        </div>
        {renderNav(collapsed)}
      </aside>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {drawer ? (
          <div className="fixed inset-0 z-50 md:hidden">
            <motion.button
              type="button"
              aria-label="Close menu"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-overlay backdrop-blur-xs"
              onClick={() => setDrawer(false)}
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 380, damping: 36 }}
              className="sidebar-ink-bg absolute inset-y-0 left-0 flex w-72 flex-col text-sidebar-foreground shadow-2xl"
            >
              <div className="flex h-[60px] items-center justify-between px-4">
                <div className="flex items-center gap-2.5">
                  <BrandMark className="h-7 w-7" />
                  <span className="text-base font-bold tracking-tight">SOPilot</span>
                </div>
                <button
                  type="button"
                  aria-label="Close menu"
                  onClick={() => setDrawer(false)}
                  className="rounded-lg p-1.5 text-sidebar-muted hover:bg-white/10 hover:text-white"
                >
                  <X size={18} aria-hidden />
                </button>
              </div>
              {renderNav(false)}
            </motion.aside>
          </div>
        ) : null}
      </AnimatePresence>

      {/* Right Workspace Column */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="surface-glass flex h-[60px] shrink-0 items-center justify-between gap-3 border-b border-border px-4">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              aria-label="Open menu"
              className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
              onClick={() => setDrawer(true)}
            >
              <Menu size={20} aria-hidden />
            </button>
            <WorkspaceSwitcher />
          </div>

          <div className="flex items-center gap-2 text-sm">
            {pendingInvites > 0 ? (
              <Link
                href="/invite"
                className="rounded-full bg-info-soft px-2.5 py-1 text-xs font-semibold text-info-foreground transition-colors hover:opacity-90"
              >
                {pendingInvites} invitation{pendingInvites === 1 ? '' : 's'}
              </Link>
            ) : null}
            <CommandMenu />
            <ThemeToggle />
            <div className="hidden items-center gap-2 rounded-xl border border-border bg-card py-1 pl-1.5 pr-2.5 sm:flex">
              <Avatar name={user.displayName} size="sm" className="h-6 w-6 rounded-lg text-[10px]" />
              <span className="max-w-[9rem] truncate text-xs font-semibold text-foreground" title={user.email}>
                {user.displayName}
              </span>
              <span className="hidden rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground md:inline">
                {workspace.role}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              aria-label="Sign out"
              icon={<LogOut size={14} aria-hidden />}
              onClick={() => {
                if (confirmDiscardUploads()) void signOut();
              }}
            >
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
