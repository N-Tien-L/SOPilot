// Fixed English labels for server codes (S4: never show a raw code or exception).

import type { AnswerWarning, DocumentStatus, KnowledgeGap } from '@/lib/api/types';

export interface RefusalCopy {
  badge: string;
  title: string;
  body: string;
  /** Only NO_EVIDENCE shows the closest documents. */
  showNearest: boolean;
}

export function refusalCopy(reason: string | null | undefined): RefusalCopy {
  switch (reason) {
    case 'NO_EVIDENCE':
      return {
        badge: 'No evidence',
        title: 'I could not find this in your SOPs',
        body: 'Nothing in the documents you can read answers this question.',
        showNearest: true,
      };
    case 'OUT_OF_SCOPE':
      return {
        badge: 'Out of scope',
        title: 'This question is outside what SOPilot answers',
        body: 'Ask about procedures in your workspace documents.',
        showNearest: false,
      };
    case 'INPUT_INVALID':
      return {
        badge: 'Cannot answer',
        title: 'This question could not be processed',
        body: 'Rephrase it, or shorten it, and try again.',
        showNearest: false,
      };
    default:
      return {
        badge: 'No answer',
        title: 'SOPilot could not answer this question',
        body: 'Try rephrasing it, or ask about a specific document.',
        showNearest: false,
      };
  }
}

/** `done.warnings`: only NUMBER_NOT_IN_SOURCES is defined today (TECH-V2-ai-service §7.2). */
export function warningText(warning: AnswerWarning): string {
  if (warning.code === 'NUMBER_NOT_IN_SOURCES') {
    return 'Check the figures against the source: a number in this answer was not found in the cited documents.';
  }
  return 'Check this answer against the cited sources.';
}

export function documentStatusLabel(status: DocumentStatus): {
  label: string;
  tone: 'success' | 'info' | 'danger';
} {
  switch (status) {
    case 'READY':
      return { label: 'Ready', tone: 'success' };
    case 'FAILED':
      return { label: 'Failed', tone: 'danger' };
    default:
      return { label: 'Processing', tone: 'info' };
  }
}

export function gapFlags(gap: Pick<KnowledgeGap, 'refusalReason' | 'downvotes'>): string[] {
  const flags: string[] = [];
  if (gap.refusalReason === 'NO_EVIDENCE') flags.push('No evidence');
  else if (gap.refusalReason) flags.push('Refused');
  if (gap.downvotes > 0) flags.push(`${gap.downvotes} downvote${gap.downvotes === 1 ? '' : 's'}`);
  return flags.length > 0 ? flags : ['Flagged'];
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
