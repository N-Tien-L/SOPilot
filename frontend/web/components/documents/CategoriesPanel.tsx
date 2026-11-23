'use client';

import { NamedListPanel } from '@/components/admin/NamedListPanel';
import { createCategory, deleteCategory, updateCategory } from '@/lib/api/endpoints';
import { useCategories } from '@/lib/query/hooks';

/** Category catalogue (OWNER and ADMIN): set up once, then picked in the document form. */
export function CategoriesPanel() {
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
      note="Flat list. Archive a category to stop new use; deleting one moves its documents to uncategorized."
    />
  );
}
