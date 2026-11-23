'use client';

import { useState } from 'react';
import { TabList, type TabItem } from '@/components/app/TabList';
import { InvitationsPanel } from '@/components/admin/InvitationsPanel';
import { MembersPanel } from '@/components/admin/MembersPanel';
import { EmptyState } from '@/components/ui';
import { useSessionStore } from '@/store/session-store';

type TabId = 'members' | 'invitations';

export default function MembersPage() {
  const workspace = useSessionStore((s) => s.workspace);
  const role = workspace?.role;
  const [tab, setTab] = useState<TabId>('members');

  if (role !== 'OWNER' && role !== 'ADMIN') {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners and admins only" description="Ask a workspace owner or admin if you need to see who is in this workspace." />
      </div>
    );
  }

  const tabs: TabItem<TabId>[] = [
    { id: 'members', label: 'Members' },
    { id: 'invitations', label: 'Invitations' },
  ];
  const current = tab;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Members</h1>
      <p className="mt-1 text-sm text-muted-foreground">People of this workspace and their invitations.</p>
      <TabList label="Workspace administration" tabs={tabs} current={current} onSelect={setTab} />
      <div className="mt-4" role="tabpanel" id={`panel-${current}`} aria-labelledby={`tab-${current}`}>
        {current === 'members' ? <MembersPanel /> : null}
        {current === 'invitations' ? <InvitationsPanel /> : null}
      </div>
    </div>
  );
}
