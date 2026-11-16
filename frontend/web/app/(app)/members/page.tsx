'use client';

import { useState } from 'react';
import { InvitationsPanel } from '@/components/admin/InvitationsPanel';
import { MembersPanel } from '@/components/admin/MembersPanel';
import { NamedListPanel } from '@/components/admin/NamedListPanel';
import { PublishersPanel } from '@/components/admin/PublishersPanel';
import { EmptyState } from '@/components/ui';
import {
  createCategory,
  createDepartment,
  deleteCategory,
  deleteDepartment,
  updateCategory,
  updateDepartment,
} from '@/lib/api/endpoints';
import { showDepartments } from '@/lib/admin/members';
import { useCategories, useDepartments, useMembers } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';

type TabId = 'members' | 'invitations' | 'departments' | 'categories' | 'publishers';

function Departments() {
  const { data, isLoading, error } = useDepartments(true);
  return (
    <NamedListPanel
      noun="department"
      items={data}
      loading={isLoading}
      error={error}
      api={{ create: createDepartment, update: updateDepartment, remove: deleteDepartment }}
      invalidate={['departments', 'members', 'publishers', 'invitations']}
      emptyHint="Departments group members and can limit who reads a document."
      note="Flat list. Archive a department to stop new assignments; delete works only while nothing uses it."
    />
  );
}

function Categories() {
  const { data, isLoading, error } = useCategories(true);
  return (
    <NamedListPanel
      noun="category"
      items={data}
      loading={isLoading}
      error={error}
      api={{ create: createCategory, update: updateCategory, remove: deleteCategory }}
      invalidate={['categories', 'documents', 'document']}
      emptyHint="Categories organise documents and appear in the document form."
      note="Flat list. Archive a category to stop new use; delete works only while no document uses it."
    />
  );
}

export default function MembersPage() {
  const workspace = useSessionStore((s) => s.workspace);
  const role = workspace?.role;
  const members = useMembers(role === 'OWNER' || role === 'ADMIN');
  const [tab, setTab] = useState<TabId>('members');

  if (role !== 'OWNER' && role !== 'ADMIN') {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners and admins only" description="Ask a workspace owner or admin if you need to see who is in this workspace." />
      </div>
    );
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: 'members', label: 'Members' },
    { id: 'invitations', label: 'Invitations' },
    ...(showDepartments(workspace?.kind, members.data ? members.data.length : null)
      ? [{ id: 'departments' as const, label: 'Departments' }]
      : []),
    { id: 'categories', label: 'Categories' },
    ...(role === 'OWNER' ? [{ id: 'publishers' as const, label: 'Publishers' }] : []),
  ];
  // A tab that disappeared (the last colleague left) falls back to the first one.
  const current = tabs.some((t) => t.id === tab) ? tab : 'members';

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Members</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        People, invitations, departments, categories{role === 'OWNER' ? ' and publishers' : ''} of this workspace.
      </p>
      <div role="tablist" aria-label="Workspace administration" className="mt-4 flex flex-wrap gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={current === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={current === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => {
              // WAI-ARIA tabs: arrows move between tabs (wrapping), Home and End jump to the ends.
              const i = tabs.findIndex((x) => x.id === t.id);
              const next =
                e.key === 'ArrowRight' ? (i + 1) % tabs.length
                : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length
                : e.key === 'Home' ? 0
                : e.key === 'End' ? tabs.length - 1
                : -1;
              if (next < 0) return;
              e.preventDefault();
              setTab(tabs[next].id);
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
      <div className="mt-4" role="tabpanel" id={`panel-${current}`} aria-labelledby={`tab-${current}`}>
        {current === 'members' ? <MembersPanel /> : null}
        {current === 'invitations' ? <InvitationsPanel /> : null}
        {current === 'departments' ? <Departments /> : null}
        {current === 'categories' ? <Categories /> : null}
        {current === 'publishers' ? <PublishersPanel /> : null}
      </div>
    </div>
  );
}
