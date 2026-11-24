'use client';

import { useState, type FormEvent } from 'react';
import { Check, Copy, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { ErrorNote } from '@/components/app/ErrorNote';
import { Badge, Button, ConfirmDialog, EmptyState, Input, Modal, Select, Skeleton } from '@/components/ui';
import { createInvitation, revokeInvitation } from '@/lib/api/endpoints';
import type { CreatedInvitation, InvitationView } from '@/lib/api/types';
import { INVITABLE_ROLES, ROLE_LABEL, blankToNull, showDepartments } from '@/lib/admin/members';
import { useDepartments, useInvalidate, useInvitations } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';
import { useAction } from './useAction';

function daysLeft(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

/** The link carries the secret token and exists only in this response: show it once, copyable. */
function CreatedLink({ created, email, onDone }: { created: CreatedInvitation; email: string; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(created.inviteUrl);
      setCopied(true);
      setCopyFailed(false);
      toast.success('Invitation link copied');
    } catch {
      setCopyFailed(true);
    }
  }
  return (
    <Modal
      open
      onClose={onDone}
      title="Invitation created"
      description={`Send this link to ${email}. It works once and expires in ${Math.max(daysLeft(created.expiresAt), 1)} days.`}
      closeOnOverlayClick={false}
    >
      <div className="space-y-3">
        <input
          readOnly
          aria-label="Invitation link"
          value={created.inviteUrl}
          onFocus={(e) => e.currentTarget.select()}
          className="h-10 w-full rounded-md border border-input bg-muted px-3 font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          This link is shown only now. If you lose it, revoke the invitation and create a new one.
        </p>
        {copyFailed ? <p role="alert" className="text-sm text-danger-foreground">Copy failed. Select the link and copy it manually.</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" icon={copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />} onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy link'}
          </Button>
          <Button variant="primary" onClick={onDone}>
            Done
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function InviteDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (c: CreatedInvitation, email: string) => void }) {
  const invalidate = useInvalidate();
  const workspace = useSessionStore((s) => s.workspace);
  const withDepartments = showDepartments(workspace?.kind);
  const departments = useDepartments(false, withDepartments);
  const { run, busy, error } = useAction();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('MEMBER');
  const [employeeCode, setEmployeeCode] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [departmentId, setDepartmentId] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    let created: CreatedInvitation | null = null;
    const input = {
      email: email.trim(),
      role,
      ...(blankToNull(employeeCode) ? { employeeCode: employeeCode.trim() } : {}),
      ...(blankToNull(jobTitle) ? { jobTitle: jobTitle.trim() } : {}),
      ...(withDepartments && departmentId ? { departmentId } : {}),
    };
    const ok = await run(async () => {
      created = await createInvitation(input);
    });
    if (ok && created) {
      await invalidate('invitations');
      onCreated(created, input.email);
    }
  }

  return (
    <Modal open onClose={onClose} title="Invite a member" description="They sign in with Google and join with the role and department you set here. Their name comes from their Google account.">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Email" type="email" required autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Select
          label="Role"
          options={INVITABLE_ROLES.map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
          value={role}
          onChange={(e) => setRole(e.target.value)}
        />
        <Input label="Employee code" maxLength={50} value={employeeCode} onChange={(e) => setEmployeeCode(e.target.value)} />
        <Input label="Job title" maxLength={100} value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
        {withDepartments ? (
          <Select
            label="Department"
            options={[{ value: '', label: 'No department' }, ...(departments.data ?? []).map((d) => ({ value: d.id, label: d.name }))]}
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
          />
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={busy} disabled={email.trim() === ''}>
            Create invitation
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function InvitationsPanel() {
  const { data, isLoading, isError, error } = useInvitations();
  const invalidate = useInvalidate();
  const [inviting, setInviting] = useState(false);
  const [created, setCreated] = useState<{ link: CreatedInvitation; email: string } | null>(null);
  const [revoking, setRevoking] = useState<InvitationView | null>(null);
  const action = useAction();

  async function revoke() {
    if (!revoking) return;
    const ok = await action.run(() => revokeInvitation(revoking.id));
    if (ok) {
      await invalidate('invitations');
      setRevoking(null);
    }
  }

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button variant="primary" icon={<Plus size={16} aria-hidden />} onClick={() => setInviting(true)}>
          Invite member
        </Button>
      </div>
      {isLoading ? <Skeleton count={3} height={40} /> : null}
      {isError ? <ErrorNote error={error} /> : null}
      {data && data.length === 0 ? <EmptyState title="No pending invitations" description="Invite someone to share this workspace." /> : null}
      {data && data.length > 0 ? (
        <div className="relative overflow-x-auto rounded-2xl border border-border bg-card shadow-[var(--shadow-sm)]">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <thead className="border-b border-border bg-muted/60 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3">Email</th>
                <th scope="col" className="px-4 py-3">Role</th>
                <th scope="col" className="px-4 py-3">Department</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/70">
              {data.map((i) => {
                const left = daysLeft(i.expiresAt);
                return (
                  <tr key={i.id} className="transition-colors hover:bg-muted/35">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground">{i.email}</div>
                      {i.displayName ? <div className="text-xs text-muted-foreground">{i.displayName}</div> : null}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={i.role === 'ADMIN' ? 'info' : 'neutral'}>{ROLE_LABEL[i.role] ?? i.role}</Badge>
                    </td>
                    <td className="px-4 py-3 text-foreground">{i.departmentName ?? '-'}</td>
                    <td className="px-4 py-3">
                      {left > 0 ? <Badge variant="info">Pending, {left}d left</Badge> : <Badge variant="neutral">Expired</Badge>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          action.reset();
                          setRevoking(i);
                        }}
                      >
                        Revoke
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {inviting ? (
        <InviteDialog
          onClose={() => setInviting(false)}
          onCreated={(link, email) => {
            setInviting(false);
            setCreated({ link, email });
          }}
        />
      ) : null}
      {created ? <CreatedLink created={created.link} email={created.email} onDone={() => setCreated(null)} /> : null}
      {revoking ? (
        <ConfirmDialog
          open
          onClose={() => setRevoking(null)}
          onConfirm={() => void revoke()}
          title="Revoke invitation"
          confirmLabel="Revoke"
          variant="danger"
          loading={action.busy}
          message={
            <>
              The link sent to <strong>{revoking.email}</strong> stops working.
              {action.error ? <ErrorNote error={action.error} className="mt-2" /> : null}
            </>
          }
        />
      ) : null}
    </>
  );
}
