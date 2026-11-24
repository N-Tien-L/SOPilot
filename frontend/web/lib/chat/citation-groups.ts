// Groups flat numeric citations [1], [2], [3] by documentId into 1.1, 1.2, 1.3 (File 1),
// 2.1 (File 2), etc., so inline badges in the answer match the grouped Sources list 1-to-1.

import type { Citation } from '@/lib/api/types';

export interface GroupedCitationItem<T extends Citation> {
  label: string;
  docIndex: number;
  citation: T;
}

export interface CitationDocumentGroup<T extends Citation> {
  docIndex: number;
  documentId: string;
  title: string;
  items: GroupedCitationItem<T>[];
}

export interface GroupedCitations<T extends Citation> {
  groups: CitationDocumentGroup<T>[];
  labelByN: Map<number, string>;
  itemByN: Map<number, GroupedCitationItem<T>>;
}

export function groupCitationsByDocument<T extends Citation>(citations: readonly T[]): GroupedCitations<T> {
  const groups: CitationDocumentGroup<T>[] = [];
  const byDoc = new Map<string, CitationDocumentGroup<T>>();
  const labelByN = new Map<number, string>();
  const itemByN = new Map<number, GroupedCitationItem<T>>();

  for (const c of citations) {
    let group = byDoc.get(c.documentId);
    if (!group) {
      group = {
        docIndex: groups.length + 1,
        documentId: c.documentId,
        title: c.title,
        items: [],
      };
      byDoc.set(c.documentId, group);
      groups.push(group);
    }
    const subIdx = group.items.length + 1;
    const label = `${group.docIndex}.${subIdx}`;
    const item: GroupedCitationItem<T> = { label, docIndex: group.docIndex, citation: c };
    group.items.push(item);
    labelByN.set(c.n, label);
    itemByN.set(c.n, item);
  }

  return { groups, labelByN, itemByN };
}
