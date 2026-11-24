// Fixed English copy for the processing report (V2-46). The API returns ids and counts, never prose.

import type { ChunkType, DocFamily, ProcessingReport } from '@/lib/api/types';

export const FAMILIES: ReadonlyArray<{ id: DocFamily; title: string; rule: string }> = [
  { id: 'LEGAL_ARTICLES', title: 'Legal articles', rule: '3 or more "Điều N" headings or lines (decrees, decisions, circulars)' },
  { id: 'ISO_PROCEDURE', title: 'Procedure (SOP)', rule: '2 or more SOP sections (purpose, scope, procedure) or a step table' },
  { id: 'MARKDOWN', title: 'Structured text', rule: 'Has headings, no special pattern' },
  { id: 'PROSE', title: 'Plain prose', rule: 'No headings at all' },
];

export function familyTitle(id: string): string {
  return FAMILIES.find((f) => f.id === id)?.title ?? id;
}

const RULES: Record<string, { title: string; detail: string }> = {
  HEADING_TREE: { title: 'Cut by heading tree', detail: 'One section is one candidate chunk.' },
  ARTICLE_UNIT: {
    title: 'One chunk per article heading',
    detail:
      'Article headings are never merged with each other; articles written as plain lines are packed like text; short lines before the first article join the next section.',
  },
  MERGE_SHORT: { title: 'Merge short sections', detail: 'A section under the minimum joins its next sibling.' },
  STEP_ROW: { title: 'Step table: one row, one chunk', detail: 'A procedure row is kept whole and never merged.' },
  PACK: { title: 'Pack text up to the target size', detail: 'Cut at a sentence once the hard cap is reached.' },
  PREFIX: { title: 'Prefix every chunk', detail: 'Title, document code and section path are embedded with the text.' },
};

export function ruleLabel(id: string): { title: string; detail: string } {
  return RULES[id] ?? { title: id, detail: '' };
}

/** What each family does differently, shown for comparison. */
export const OTHER_FAMILY_NOTES: Record<DocFamily, string> = {
  LEGAL_ARTICLES: 'One chunk per article heading; short lines before the first article are merged.',
  ISO_PROCEDURE: 'Heading sections, one chunk per step-table row.',
  MARKDOWN: 'Heading sections, short ones merged.',
  PROSE: 'Paragraphs packed to the token target.',
};

export const CHUNK_TYPE_LABEL: Record<ChunkType, string> = {
  SECTION: 'Section',
  PROSE: 'Prose',
  PROCEDURE_STEP: 'Procedure step',
  TABLE: 'Table',
};

/** Outline colours by chunk type (Tailwind palette, readable on the light and dark themes). */
export function chunkTypeClasses(type: ChunkType): { box: string; text: string; swatch: string } {
  switch (type) {
    case 'PROCEDURE_STEP':
      return { box: 'border-green-600 bg-green-500/10', text: 'text-green-700 dark:text-green-400', swatch: 'border-green-600' };
    case 'TABLE':
      return { box: 'border-orange-600 bg-orange-500/10', text: 'text-orange-700 dark:text-orange-400', swatch: 'border-orange-600' };
    default:
      return { box: 'border-blue-600 bg-blue-500/10', text: 'text-blue-700 dark:text-blue-400', swatch: 'border-blue-600' };
  }
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The evidence behind the detected family, as short lines. */
export function signalLines(report: Pick<ProcessingReport, 'signals' | 'language' | 'docCode'>): string[] {
  const lines: string[] = [];
  const s = report.signals;
  if (!s) {
    lines.push('The evidence could not be recomputed for this version.');
  } else {
    lines.push(plural(s.headings, 'heading'));
    lines.push(`${plural(s.articleHeadings, 'article heading')} ("Điều N")`);
    if (s.articleLines > 0) lines.push(`${plural(s.articleLines, 'article line')} in the body text`);
    lines.push(
      s.sopSectionWords.length > 0
        ? `SOP section words: ${s.sopSectionWords.join(', ')}`
        : 'No SOP section words in the headings',
    );
    lines.push(plural(s.procedureTables, 'step table'));
  }
  if (report.language) lines.push(`Language: ${report.language}`);
  if (report.docCode) lines.push(`Document code: ${report.docCode}`);
  return lines;
}

export function pageLabelOf(index: number, total: number, label: string): string {
  return `${label} (${index + 1} of ${total})`;
}
