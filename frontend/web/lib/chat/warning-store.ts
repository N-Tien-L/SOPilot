// `done.warnings` (for example NUMBER_NOT_IN_SOURCES) and a refusal's `nearestDocuments` exist only
// in the live stream: the history endpoint returns neither. Keep them in memory per message so
// they survive the reload of the conversation that follows an answer. Lost on page reload, and
// cleared on a workspace switch (R7). Holds codes, values and document titles, never answer text.

import type { AnswerWarning } from '@/lib/api/types';

const byMessage = new Map<string, AnswerWarning[]>();
const nearestByMessage = new Map<string, NearestDocument[]>();

export interface NearestDocument {
  documentId: string;
  title: string;
}

export function rememberWarnings(messageId: string | null, warnings: AnswerWarning[]): void {
  if (messageId && warnings.length > 0) byMessage.set(messageId, warnings);
}

export function recallWarnings(messageId: string): AnswerWarning[] {
  return byMessage.get(messageId) ?? [];
}

export function rememberNearest(messageId: string | null, docs: NearestDocument[]): void {
  if (messageId && docs.length > 0) nearestByMessage.set(messageId, docs);
}

export function recallNearest(messageId: string): NearestDocument[] {
  return nearestByMessage.get(messageId) ?? [];
}

export function clearWarnings(): void {
  byMessage.clear();
  nearestByMessage.clear();
}
