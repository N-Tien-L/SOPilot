// TanStack Query hooks for the V2-15 screens. Every key starts with the workspace id (M5, R7).

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as api from '@/lib/api/endpoints';
import type { DocumentFilters } from '@/lib/api/endpoints';
import { useSessionStore } from '@/store/session-store';
import { workspaceKey } from './client';

function useWid(): string {
  return useSessionStore((s) => s.workspace?.id ?? 'none');
}

export function useWorkspaces() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'workspaces'), queryFn: api.listWorkspaces });
}

export function useWorkspaceDetail() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'workspace'), queryFn: api.getWorkspace });
}

export function useMembers() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'members'), queryFn: api.listMembers });
}

/** The caller's own membership, including what they may publish. */
export function useMyMember() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'member-me'), queryFn: api.getMyMember });
}

export function useInvitations() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'invitations'), queryFn: api.listInvitations });
}

export function useCategories() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'categories'), queryFn: api.listCategories });
}

/** R3: polls only while some loaded document is still UPLOADED or PROCESSING. */
export function useDocuments(filters: Omit<DocumentFilters, 'cursor'>) {
  const wid = useWid();
  return useInfiniteQuery({
    queryKey: workspaceKey(wid, 'documents', filters),
    queryFn: ({ pageParam }) => api.listDocuments({ ...filters, ...(pageParam ? { cursor: pageParam } : {}) }),
    initialPageParam: '' as string,
    getNextPageParam: (last) => (last.page.hasMore && last.page.cursor ? last.page.cursor : undefined),
    refetchInterval: (query) => {
      const pages = query.state.data?.pages ?? [];
      const busy = pages.some((p) => p.data.some((d) => d.status === 'UPLOADED' || d.status === 'PROCESSING'));
      return busy ? 5000 : false;
    },
  });
}

/** One document with its current and latest version (404 when outside access). */
export function useDocument(id: string) {
  const wid = useWid();
  return useQuery({
    queryKey: workspaceKey(wid, 'document', id),
    queryFn: ({ signal }) => api.getDocument(id, signal),
    retry: false,
    // A newer version may be processing: keep the label fresh until it settles.
    refetchInterval: (query) => {
      const d = query.state.data;
      return d && (d.latestVersion.status === 'UPLOADED' || d.latestVersion.status === 'PROCESSING') ? 5000 : false;
    },
  });
}

/** The canonical Markdown of the active version. No retry: a 404 is the answer (FR-25). */
export function useDocumentContent(documentId: string, versionId: string | null) {
  const wid = useWid();
  return useQuery({
    queryKey: workspaceKey(wid, 'content', documentId, versionId),
    queryFn: ({ signal }) => api.getDocumentContent(documentId, versionId as string, signal),
    enabled: versionId !== null,
    retry: false,
    // Never serve cached content without asking: access may have been revoked (FR-25).
    staleTime: 0,
    refetchOnMount: 'always',
  });
}

export function useConversations() {
  const wid = useWid();
  return useQuery({ queryKey: workspaceKey(wid, 'conversations'), queryFn: () => api.listConversations() });
}

export function useConversation(id: string | null) {
  const wid = useWid();
  return useQuery({
    queryKey: workspaceKey(wid, 'conversation', id),
    queryFn: () => api.getConversation(id as string),
    enabled: id !== null,
  });
}

export function useKnowledgeGaps(status: 'open' | 'resolved', pageSize: number, enabled = true) {
  const wid = useWid();
  return useInfiniteQuery({
    queryKey: workspaceKey(wid, 'gaps', status),
    queryFn: ({ pageParam }) => api.listKnowledgeGaps(status, pageSize, pageParam),
    initialPageParam: 0,
    enabled,
    // The API has no total or hasMore: a full page means there may be more.
    getNextPageParam: (last, all) => (last.length === pageSize ? all.length * pageSize : undefined),
  });
}

/** Invalidate everything of this workspace that matches a key prefix. */
export function useInvalidate() {
  const client = useQueryClient();
  const wid = useWid();
  return (...parts: readonly unknown[]) =>
    client.invalidateQueries({ queryKey: workspaceKey(wid, ...parts) });
}

export { useMutation };
