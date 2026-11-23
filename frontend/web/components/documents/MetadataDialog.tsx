'use client';

import { useState, type FormEvent } from 'react';
import { ErrorNote } from '@/components/app/ErrorNote';
import { useAction } from '@/components/admin/useAction';
import { Button, Checkbox, Input, Modal, Select, Textarea } from '@/components/ui';
import {
  createCategory,
  transferDocumentOwnership,
  updateDocument,
  updateDocumentVisibility,
} from '@/lib/api/endpoints';
import type { DocumentView } from '@/lib/api/types';
import { showDepartments } from '@/lib/admin/members';
import {
  buildDocumentPatch,
  formFromDocument,
  sourceLabel,
  planAccess,
  canWriteDocument,
  validateMetadata,
  type MetadataForm,
  type VisibilityChoice,
} from '@/lib/admin/metadata';
import { useCategories, useDepartments, useInvalidate, useMyMember } from '@/lib/query/hooks';
import { useSessionStore } from '@/store/session-store';

function FieldNote({ source }: { source: string | null | undefined }) {
  const text = sourceLabel(source);
  return text ? <span className="text-xs text-muted-foreground">{text}</span> : null;
}

function ReadOnlyFact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value || '-'}</dd>
    </div>
  );
}

/**
 * One editable form pre-filled from the document (V2-25 §2a). Details and access save separately,
 * so a refused access change never loses the metadata that was saved. Nothing here blocks upload
 * or chat: the dialog is optional and suggestions are only offered, never forced.
 */
export function MetadataDialog({ doc, onClose }: { doc: DocumentView; onClose: () => void }) {
  const invalidate = useInvalidate();
  const workspace = useSessionStore((s) => s.workspace);
  const isManager = workspace?.role === 'OWNER' || workspace?.role === 'ADMIN';
  const categories = useCategories();
  const withDepartments = showDepartments(workspace?.kind);
  const departments = useDepartments(false, withDepartments);

  const [form, setForm] = useState<MetadataForm>(() => formFromDocument(doc));
  const [touched, setTouched] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const details = useAction();
  const access = useAction();
  const category = useAction();

  const [visibility, setVisibility] = useState<VisibilityChoice>(doc.visibility === 'DEPARTMENTS' ? 'DEPARTMENTS' : 'WORKSPACE');
  const [departmentIds, setDepartmentIds] = useState<string[]>((doc.departments ?? []).map((d) => d.id));
  const [ownerDeptId, setOwnerDeptId] = useState<string>(doc.ownerDepartment?.id ?? '');
  const isOwner = workspace?.role === 'OWNER';
  const me = useMyMember();
  const canWrite = canWriteDocument(me.data?.publisherOf, doc);

  const categoryList = categories.data ?? [];
  const errors = validateMetadata(form, categoryList.length > 0);
  const patch = buildDocumentPatch(doc, form);
  const dirty = Object.keys(patch).length > 0;
  const processing = doc.latestVersion.status === 'UPLOADED' || doc.latestVersion.status === 'PROCESSING';
  const suggestedTitle = doc.suggestions?.title && doc.suggestions.title !== form.title ? doc.suggestions.title : null;
  const proposed = doc.suggestions?.proposedCategoryName ?? null;
  const proposedExists = proposed ? categoryList.some((c) => c.name.toLowerCase() === proposed.toLowerCase()) : false;

  const categoryOptions = categoryList.map((c) => ({ value: c.id, label: c.name }));
  if (doc.category && !categoryOptions.some((o) => o.value === doc.category?.id)) {
    categoryOptions.push({ value: doc.category.id, label: `${doc.category.name} (archived)` });
  }

  async function saveDetails(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    setSaved(null);
    if (Object.keys(errors).length > 0 || !dirty) return;
    const ok = await details.run(() => updateDocument(doc.id, patch));
    if (ok) {
      await invalidate('documents');
      await invalidate('document', doc.id);
      await invalidate('categories');
      onClose();
    }
  }

  async function createSuggestedCategory() {
    if (!proposed) return;
    let createdId: string | null = null;
    const ok = await category.run(async () => {
      createdId = (await createCategory(proposed)).id;
    });
    if (ok && createdId) {
      await invalidate('categories');
      setForm((f) => ({ ...f, categoryId: createdId as string }));
    }
  }

  const plan = planAccess(doc, { visibility, departmentIds, ownerDepartmentId: ownerDeptId || null }, { isOwner, canWrite });
  // `doc` is the list's copy and does not refresh while the dialog is open: remember what was saved so
  // the same selection is not sent twice.
  const selection = JSON.stringify([visibility, [...departmentIds].sort(), ownerDeptId]);
  const [savedSelection, setSavedSelection] = useState<string | null>(null);

  async function saveAccess() {
    setSaved(null);
    if (plan.action !== 'visibility' && plan.action !== 'transfer') return;
    let sync: string | null = null;
    let unattended = false;
    const ok = await access.run(async () => {
      if (plan.action === 'visibility') {
        sync = (await updateDocumentVisibility(doc.id, plan.visibility, plan.departmentIds)).accessSync;
      } else if (plan.action === 'transfer') {
        const res = await transferDocumentOwnership(doc.id, {
          visibility: plan.visibility,
          ownerDepartmentId: plan.ownerDepartmentId,
          departmentIds: plan.departmentIds,
        });
        sync = res.accessSync;
        unattended = !res.publisherAssigned;
      }
    });
    if (ok) {
      setSavedSelection(selection);
      await invalidate('documents');
      await invalidate('document', doc.id);
      const base =
        sync === 'PENDING'
          ? 'Access saved. It is still reaching search and answers, which can take a moment.'
          : 'Access saved and applied.';
      setSaved(
        unattended
          ? `${base} Nobody is assigned to publish in the new scope yet: assign a publisher under Departments.`
          : base,
      );
    }
  }

  const set = (key: keyof MetadataForm) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const shown = (key: 'description' | 'categoryId') => (touched ? errors[key] : undefined);

  return (
    <Modal open onClose={onClose} title="Document details" description={doc.title} size="lg">
      <div className="space-y-6">
        {processing ? (
          <p role="status" className="rounded-md bg-info-soft p-3 text-sm text-info-foreground">
            This document is still being processed. Suggested values appear here when it is ready; you can edit now.
          </p>
        ) : null}
        {doc.status === 'FAILED' ? (
          <p role="status" className="rounded-md bg-warning-soft p-3 text-sm text-warning-foreground">
            Processing failed, so no suggestions were made. You can still edit the details.
          </p>
        ) : null}

        {!canWrite ? (
          // Focusable on purpose: the Modal moves focus to its first focusable element, and fields inside
          // the disabled fieldset below cannot take it, so the explanation is where focus lands.
          <p
            role="note"
            tabIndex={0}
            className="rounded-md bg-muted p-3 text-sm text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
          >
            Only the publisher responsible for this document edits its details.
            {isOwner ? ' As an owner you can transfer responsibility or change who reads it below.' : ''}
          </p>
        ) : null}

        <form onSubmit={saveDetails} className="space-y-3" aria-label="Metadata">
          <fieldset disabled={!canWrite} className="min-w-0 space-y-3 border-0 p-0">
          <div>
            <Input
              label="Title"
              maxLength={200}
              value={form.title}
              onChange={(e) => set('title')(e.target.value)}
              helperText="Leave empty to keep the current title."
            />
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <FieldNote source={doc.fieldSources?.title} />
              {suggestedTitle ? (
                <Button type="button" size="sm" variant="ghost" onClick={() => set('title')(suggestedTitle)}>
                  Use suggested title: {suggestedTitle}
                </Button>
              ) : null}
            </div>
          </div>
          <div>
            <Textarea
              label="Description"
              rows={3}
              maxLength={2000}
              value={form.description}
              onChange={(e) => set('description')(e.target.value)}
              error={shown('description')}
            />
            <FieldNote source={doc.fieldSources?.description} />
          </div>
          <div>
            <Select
              label="Category"
              placeholder={categoryOptions.length === 0 ? 'No categories yet' : 'Choose a category'}
              options={categoryOptions}
              value={form.categoryId}
              onChange={(e) => set('categoryId')(e.target.value)}
              error={shown('categoryId')}
              disabled={categoryOptions.length === 0}
            />
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <FieldNote source={doc.fieldSources?.category} />
              {proposed && !proposedExists ? (
                isManager ? (
                  <Button type="button" size="sm" variant="ghost" loading={category.busy} onClick={() => void createSuggestedCategory()}>
                    Create suggested category: {proposed}
                  </Button>
                ) : (
                  <span className="text-xs text-muted-foreground">Suggested new category: {proposed} (an admin can create it)</span>
                )
              ) : null}
            </div>
            {category.error ? <ErrorNote error={category.error} /> : null}
          </div>
          <div>
            <Input
              label="Prepared by"
              maxLength={100}
              value={form.preparedBy}
              onChange={(e) => set('preparedBy')(e.target.value)}
              helperText="Who drafted the content: a department, a person or a source. Readers see it."
            />
          </div>
          <div>
            <Input
              label="Language"
              maxLength={10}
              value={form.language}
              onChange={(e) => set('language')(e.target.value)}
              helperText="For example en or vi."
            />
            <FieldNote source={doc.fieldSources?.language} />
          </div>

          <div className="rounded-md border border-border bg-muted p-3">
            <p className="mb-2 text-xs text-muted-foreground">Extracted automatically, may be wrong. Not editable here.</p>
            <dl className="grid gap-3 sm:grid-cols-3">
              <ReadOnlyFact label="Document code" value={doc.currentVersion?.docCode} />
              <ReadOnlyFact label="Revision" value={doc.currentVersion?.revisionLabel} />
              <ReadOnlyFact label="Effective date" value={doc.currentVersion?.effectiveDate} />
            </dl>
          </div>

          </fieldset>

          {details.error ? <ErrorNote error={details.error} /> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
            <Button type="submit" variant="primary" loading={details.busy} disabled={!dirty || !canWrite}>
              Save details
            </Button>
          </div>
        </form>

        <section aria-labelledby="access-heading" className="space-y-3 border-t border-border pt-4">
          <h3 id="access-heading" className="text-base font-semibold">Who can read this</h3>
          <div role="radiogroup" aria-label="Scope" className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="scope" checked={visibility === 'WORKSPACE'} onChange={() => setVisibility('WORKSPACE')} />
              Everyone in the workspace
            </label>
            {withDepartments ? (
              <label className="flex items-center gap-2">
                <input type="radio" name="scope" checked={visibility === 'DEPARTMENTS'} onChange={() => setVisibility('DEPARTMENTS')} />
                Selected departments only
              </label>
            ) : null}
          </div>
          {visibility === 'DEPARTMENTS' ? (
            <div className="space-y-2 pl-6">
              {(departments.data ?? []).map((d) => {
                const isOwning = d.id === (ownerDeptId || doc.ownerDepartment?.id);
                return (
                  <Checkbox
                    key={d.id}
                    label={isOwning ? `${d.name} (owning department)` : d.name}
                    checked={departmentIds.includes(d.id) || isOwning}
                    disabled={isOwning}
                    onChange={(e) =>
                      setDepartmentIds((ids) => (e.target.checked ? [...ids, d.id] : ids.filter((id) => id !== d.id)))
                    }
                  />
                );
              })}
              {departments.data && departments.data.length === 0 ? (
                <p className="text-sm text-muted-foreground">Create a department first (Departments in the sidebar).</p>
              ) : null}
              {isOwner ? (
                <Select
                  label="Owning department"
                  placeholder="Choose the owning department"
                  options={(departments.data ?? [])
                    .filter((d) => departmentIds.includes(d.id) || d.id === ownerDeptId)
                    .map((d) => ({ value: d.id, label: d.name }))}
                  value={ownerDeptId}
                  onChange={(e) => setOwnerDeptId(e.target.value)}
                  helperText="Its publisher manages this document. Changing it is a transfer of responsibility."
                />
              ) : null}
            </div>
          ) : null}
          {plan.action === 'blocked' ? (
            <p role="note" className="text-sm text-warning-foreground">{plan.reason}</p>
          ) : null}
          {plan.action === 'transfer' ? (
            <p role="note" className="text-sm text-muted-foreground">
              This moves responsibility for the document. Its content, versions and history stay.
            </p>
          ) : null}
          {access.error ? <ErrorNote error={access.error} /> : null}
          {saved ? <p role="status" className="text-sm text-success-foreground">{saved}</p> : null}
          <div className="flex justify-end">
            <Button
              variant="primary"
              loading={access.busy}
              disabled={(plan.action !== 'visibility' && plan.action !== 'transfer') || selection === savedSelection}
              onClick={() => void saveAccess()}
            >
              {plan.action === 'transfer' ? 'Transfer responsibility' : 'Save access'}
            </Button>
          </div>
        </section>
      </div>
    </Modal>
  );
}
