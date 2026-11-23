'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Building2, FileText, Flag, LogOut, Menu, MessageSquare, ScrollText, Settings, Users, X } from 'lucide-react';
import { Button } from '@/components/ui';
import { ConversationList } from '@/components/chat/ConversationList';
import { showDepartments } from '@/lib/admin/members';
import { restoreSession, signOut } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { useSessionStore } from '@/store/session-store';
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

  useEffect(() => {
    if (status === 'anonymous') router.replace('/login');
  }, [status, router]);

  if (status === 'unreachable') {
    return (
      <main className="mx-auto max-w-md p-8 text-sm">
        <p role="alert">The server could not be reached. Your session is kept; try again.</p>
        <div className="mt-4">
          <Button variant="outline" onClick={() => void restoreSession()}>
            Retry
          </Button>
        </div>
      </main>
    );
  }
  if (status !== 'authenticated' || !user || !workspace) {
    return <main className="p-8 text-sm text-muted-foreground">Loading…</main>;
  }

  const items = NAV.filter(
    (n) => (!n.roles || n.roles.includes(workspace.role)) && !(n.teamOnly && !showDepartments(workspace.kind)),
  );
  const nav = (
    <nav
      aria-label="Main"
      className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-3"
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
            className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm ${
              active ? 'bg-white/15 font-semibold text-sidebar-foreground' : 'text-sidebar-muted hover:bg-white/10'
            }`}
          >
            {item.icon}
            {item.label}
          </Link>
        );
      })}
      <div className="my-3 border-t border-white/15" />
      <ConversationList />
    </nav>
  );

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <aside className="hidden w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground md:flex">
        <div className="px-6 pb-2 pt-5 text-lg font-bold">SOPilot</div>
        {nav}
      </aside>
      {drawer ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-black/50"
            onClick={() => setDrawer(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-sidebar text-sidebar-foreground">
            <div className="flex items-center justify-between px-6 pb-2 pt-5">
              <span className="text-lg font-bold">SOPilot</span>
              <button type="button" aria-label="Close menu" onClick={() => setDrawer(false)}>
                <X size={18} aria-hidden />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      ) : null}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border bg-card px-4 py-2.5">
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Open menu"
              className="rounded-md p-1.5 hover:bg-muted md:hidden"
              onClick={() => setDrawer(true)}
            >
              <Menu size={20} aria-hidden />
            </button>
            <WorkspaceSwitcher />
          </div>
          <div className="flex items-center gap-3 text-sm">
            {pendingInvites > 0 ? (
              <Link href="/invite" className="rounded-full bg-info-soft px-2.5 py-0.5 text-xs font-semibold text-info-foreground">
                {pendingInvites} invitation{pendingInvites === 1 ? '' : 's'}
              </Link>
            ) : null}
            <span className="hidden rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground sm:inline">
              {workspace.role}
            </span>
            <span className="hidden max-w-[12rem] truncate text-muted-foreground sm:inline" title={user.email}>
              {user.displayName}
            </span>
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
