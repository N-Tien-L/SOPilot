'use client';

import React, { useEffect, useState } from 'react';
import { Search, Plus, MessageSquare, Trash2, X, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { clsx } from 'clsx';
import { Button, Input, ConfirmDialog } from '@/components/ui';
import { useConversations, useDeleteConversation } from '@/hooks/useChat';
import type { Conversation } from '@/types';

interface ChatSidebarProps {
  selectedId?: string;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) {
    return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  } else if (days === 1) {
    return 'Hôm qua';
  } else if (days < 7) {
    return `${days} ngày trước`;
  } else {
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
  }
}

function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength) + '...';
}

export function ChatSidebar({
  selectedId,
  onSelect,
  onNewChat,
  isOpen,
  onClose,
  collapsed,
  onToggleCollapse,
}: ChatSidebarProps) {
  const [search, setSearch] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);
  const { data, isLoading } = useConversations({ keyword: search || undefined });
  const deleteMutation = useDeleteConversation();

  useEffect(() => {
    const handleResize = () => {
      // Auto-collapse chat sidebar on narrow viewports is handled at parent level if needed.
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleDelete = async () => {
    if (deleteTarget) {
      await deleteMutation.mutateAsync(deleteTarget.id);
      if (selectedId === deleteTarget.id) {
        onSelect('');
      }
      setDeleteTarget(null);
    }
  };

  return (
    <>
      <aside
        className={clsx(
          'fixed lg:relative z-40 h-full bg-background border-r border-border flex flex-col transition-[width,transform] duration-300',
          collapsed ? 'w-0 lg:w-16' : 'w-72 lg:w-80',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        )}
      >
        {/* Single collapse/expand button at the top - mirrors MainLayout Sidebar pattern */}
        <div className={clsx(
          'hidden lg:flex items-center border-b border-border h-10 flex-shrink-0',
          collapsed ? 'justify-center px-2' : 'justify-between px-3'
        )}>
          {!collapsed && (
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Lịch sử
            </span>
          )}
          <button
            onClick={onToggleCollapse}
            className="p-1.5 hover:bg-accent rounded-md transition-colors text-muted-foreground hover:text-foreground"
            aria-label={collapsed ? 'Expand history panel' : 'Collapse history panel'}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {!collapsed && (
          <>
            <div className="px-3 pt-3 pb-2">
              <Button
                variant="outline"
                fullWidth
                onClick={onNewChat}
                icon={<Plus size={16} />}
                className="justify-start"
              >
                Cuộc trò chuyện mới
              </Button>
            </div>

            <div className="px-3 pb-2">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Tìm kiếm..."
                  className="w-full pl-9 pr-3 py-2 bg-muted border border-input rounded-lg text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-3 pb-3">
              {isLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 bg-muted rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : !data?.conversations?.length ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
                  <p>Chưa có cuộc trò chuyện nào</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {data.conversations.map((conv) => (
                    <div
                      key={conv.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelect(conv.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onSelect(conv.id);
                        }
                      }}
                      className={clsx(
                        'w-full text-left p-3 rounded-lg transition-colors group relative cursor-pointer',
                        selectedId === conv.id
                          ? 'bg-primary/10 text-primary'
                          : 'hover:bg-accent text-foreground'
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare
                          size={16}
                          className={clsx(
                            'flex-shrink-0 mt-0.5',
                            selectedId === conv.id ? 'text-primary' : 'text-muted-foreground'
                          )}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {truncate(conv.title || 'Cuộc trò chuyện mới', 48)}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-muted-foreground">
                              {formatDate(conv.lastMessageAt)}
                            </span>
                            <span className="text-xs text-muted-foreground/70">
                              · {conv.messageCount} tin nhắn
                            </span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(conv);
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 rounded transition-all text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {collapsed && (
          <div className="flex-1 overflow-y-auto w-full flex flex-col items-center gap-1 px-2 py-3 hidden lg:flex">
            <button
              onClick={onNewChat}
              className="w-10 h-10 rounded-lg flex items-center justify-center transition-colors text-primary hover:bg-accent"
              aria-label="New conversation"
              title="New conversation"
            >
              <Plus size={18} />
            </button>
            <div className="h-px w-8 bg-border my-1" />
            {!data?.conversations?.length ? null : (
              <>
                {data.conversations.slice(0, 30).map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => onSelect(conv.id)}
                    className={clsx(
                      'w-10 h-10 rounded-lg flex items-center justify-center transition-colors',
                      selectedId === conv.id
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-accent text-muted-foreground'
                    )}
                    title={conv.title || 'Cuộc trò chuyện mới'}
                    aria-label={conv.title || 'Cuộc trò chuyện mới'}
                  >
                    <MessageSquare size={16} />
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </aside>

      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 lg:hidden z-30"
          onClick={onClose}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Xóa cuộc trò chuyện"
        message={`Bạn có chắc muốn xóa "${deleteTarget?.title || 'cuộc trò chuyện này'}"? Hành động này không thể hoàn tác.`}
        confirmLabel="Xóa"
        cancelLabel="Hủy"
        variant="danger"
        onConfirm={handleDelete}
        loading={deleteMutation.isLoading}
      />
    </>
  );
}

export default ChatSidebar;