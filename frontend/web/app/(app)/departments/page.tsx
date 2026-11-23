'use client';

import { DepartmentsPanel } from '@/components/admin/DepartmentsPanel';
import { EmptyState } from '@/components/ui';
import { showDepartments } from '@/lib/admin/members';
import { useSessionStore } from '@/store/session-store';

export default function DepartmentsPage() {
  const workspace = useSessionStore((s) => s.workspace);
  const role = workspace?.role;

  if (role !== 'OWNER' && role !== 'ADMIN') {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="Owners and admins only" description="Ask a workspace owner or admin about departments and their publishers." />
      </div>
    );
  }
  if (!showDepartments(workspace?.kind)) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState title="No departments here" description="A personal workspace has no departments. Create a team workspace to use them." />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold">Departments</h1>
      <p className="mt-1 text-sm text-muted-foreground">Departments, the people in them and who publishes for each.</p>
      <div className="mt-4">
        <DepartmentsPanel />
      </div>
    </div>
  );
}
