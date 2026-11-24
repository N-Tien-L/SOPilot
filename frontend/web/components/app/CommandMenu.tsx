'use client';

import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { AnimatePresence, motion } from 'motion/react';
import { Command } from 'cmdk';
import { useTheme } from 'next-themes';
import {
  Building2,
  Command as CommandIcon,
  FileText,
  Flag,
  LayoutGrid,
  MessageSquare,
  Moon,
  Plus,
  ScrollText,
  Search,
  Settings,
  Sun,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import { showDepartments } from '@/lib/admin/members';
import { useConversations, useWorkspaces } from '@/lib/query/hooks';
import { switchWorkspace } from '@/lib/session/auth';
import { confirmDiscardUploads } from '@/lib/upload/guard';
import { useSessionStore } from '@/store/session-store';

const subscribeNoop = () => () => {};

export function CommandMenu() {
  const router = useRouter();
  const workspace = useSessionStore((s) => s.workspace);
  const { data: conversations } = useConversations();
  const { data: workspaces } = useWorkspaces();
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribeNoop, () => true, () => false);
  const [open, setOpen] = useState(false);

  const isDark = mounted && resolvedTheme === 'dark';

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const role = workspace?.role ?? 'MEMBER';
  const canManage = role === 'OWNER' || role === 'ADMIN';
  const hasDepts = canManage && showDepartments(workspace?.kind);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  async function pickWorkspace(id: string, name: string) {
    setOpen(false);
    if (id === workspace?.id) return;
    if (!confirmDiscardUploads()) return;
    try {
      await switchWorkspace(id);
      toast.success(`Switched to ${name}`);
      router.push('/chat');
    } catch {
      toast.error('Could not switch workspace');
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open command menu"
        className="hidden h-9 cursor-pointer items-center gap-2 rounded-xl border border-border bg-muted/60 px-3 text-xs text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:inline-flex"
      >
        <Search size={13} aria-hidden />
        <span>Quick jump…</span>
        <kbd className="ml-2 inline-flex items-center gap-0.5 rounded-md border border-border bg-card px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground">
          <CommandIcon size={9} aria-hidden />K
        </kbd>
      </button>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <AnimatePresence>
          {open ? (
            <Dialog.Portal forceMount>
              <Dialog.Overlay asChild>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-50 bg-overlay backdrop-blur-xs"
                />
              </Dialog.Overlay>
              <Dialog.Content asChild>
                <motion.div
                  initial={{ opacity: 0, scale: 0.96, y: -8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.96, y: -8 }}
                  transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
                  className="fixed left-1/2 top-[16%] z-50 w-[min(92vw,34rem)] -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-card-elevated shadow-[var(--shadow-lg)] focus:outline-none"
                >
                  <Dialog.Title className="sr-only">Command menu</Dialog.Title>
                  <Command className="flex flex-col">
                    <div className="flex items-center gap-2.5 border-b border-border px-4">
                      <Search size={15} aria-hidden className="text-muted-foreground" />
                      <Command.Input
                        placeholder="Jump to a page, conversation, or workspace…"
                        className="h-12 flex-1 bg-transparent text-sm text-foreground placeholder:text-placeholder focus:outline-none"
                      />
                    </div>
                    <Command.List className="max-h-80 overflow-y-auto p-2 text-sm">
                      <Command.Empty className="py-6 text-center text-xs text-muted-foreground">
                        No matching results.
                      </Command.Empty>

                      <Command.Group
                        heading="Navigation"
                        className="px-2 py-1 text-[11px] font-semibold text-muted-foreground"
                      >
                        <Command.Item
                          onSelect={() => go('/chat')}
                          className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                        >
                          <Plus size={14} aria-hidden /> New chat
                        </Command.Item>
                        <Command.Item
                          onSelect={() => go('/documents')}
                          className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                        >
                          <FileText size={14} aria-hidden /> Documents
                        </Command.Item>
                        {canManage ? (
                          <Command.Item
                            onSelect={() => go('/members')}
                            className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                          >
                            <Users size={14} aria-hidden /> Members &amp; invitations
                          </Command.Item>
                        ) : null}
                        {hasDepts ? (
                          <Command.Item
                            onSelect={() => go('/departments')}
                            className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                          >
                            <Building2 size={14} aria-hidden /> Departments &amp; publishers
                          </Command.Item>
                        ) : null}
                        {canManage ? (
                          <Command.Item
                            onSelect={() => go('/gaps')}
                            className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                          >
                            <Flag size={14} aria-hidden /> Knowledge gaps
                          </Command.Item>
                        ) : null}
                        {role === 'OWNER' ? (
                          <Command.Item
                            onSelect={() => go('/audit')}
                            className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                          >
                            <ScrollText size={14} aria-hidden /> Audit log
                          </Command.Item>
                        ) : null}
                        <Command.Item
                          onSelect={() => go('/settings')}
                          className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                        >
                          <Settings size={14} aria-hidden /> Workspace settings
                        </Command.Item>
                        <Command.Item
                          onSelect={() => go('/workspaces')}
                          className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                        >
                          <LayoutGrid size={14} aria-hidden /> All workspaces
                        </Command.Item>
                      </Command.Group>

                      {conversations && conversations.length > 0 ? (
                        <Command.Group
                          heading="Recent conversations"
                          className="mt-2 px-2 py-1 text-[11px] font-semibold text-muted-foreground"
                        >
                          {conversations.slice(0, 6).map((c) => (
                            <Command.Item
                              key={c.id}
                              value={`chat ${c.title ?? 'New conversation'} ${c.id}`}
                              onSelect={() => go(`/chat/${c.id}`)}
                              className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                            >
                              <MessageSquare size={14} aria-hidden className="shrink-0" />
                              <span className="truncate">{c.title || 'New conversation'}</span>
                            </Command.Item>
                          ))}
                        </Command.Group>
                      ) : null}

                      {workspaces && workspaces.length > 1 ? (
                        <Command.Group
                          heading="Switch workspace"
                          className="mt-2 px-2 py-1 text-[11px] font-semibold text-muted-foreground"
                        >
                          {workspaces.map((w) => (
                            <Command.Item
                              key={w.id}
                              value={`workspace ${w.name}`}
                              onSelect={() => void pickWorkspace(w.id, w.name)}
                              className="flex cursor-pointer items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                            >
                              <span className="truncate">{w.name}</span>
                              <span className="text-xs text-muted-foreground">
                                {w.id === workspace?.id ? 'Current' : w.role}
                              </span>
                            </Command.Item>
                          ))}
                        </Command.Group>
                      ) : null}

                      <Command.Group
                        heading="Appearance"
                        className="mt-2 px-2 py-1 text-[11px] font-semibold text-muted-foreground"
                      >
                        <Command.Item
                          onSelect={() => {
                            setTheme(isDark ? 'light' : 'dark');
                            setOpen(false);
                          }}
                          className="flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-foreground aria-selected:bg-primary-soft aria-selected:text-primary-strong"
                        >
                          {isDark ? <Sun size={14} aria-hidden /> : <Moon size={14} aria-hidden />}
                          Switch to {isDark ? 'light' : 'dark'} mode
                        </Command.Item>
                      </Command.Group>
                    </Command.List>
                  </Command>
                </motion.div>
              </Dialog.Content>
            </Dialog.Portal>
          ) : null}
        </AnimatePresence>
      </Dialog.Root>
    </>
  );
}
