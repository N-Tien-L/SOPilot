import { create } from 'zustand';
import type { SourceDocument, ChunkRef } from '@/types';

interface DocumentViewerState {
  isOpen: boolean;
  documentId: string;
  documentName: string;
  /** chunk excerpts to highlight in the full-text reader */
  highlights: string[];
  /** structured chunk data for the chunks-only fallback view */
  chunks: ChunkRef[];
}

interface UIState {
  sidebarOpen: boolean;
  currentPage: string;
  theme: 'light' | 'dark';

  // Sources sidebar state
  isSourcesPanelOpen: boolean;
  activeMessageSources: SourceDocument[];

  // Document viewer modal state
  activeDocumentViewer: DocumentViewerState;

  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setCurrentPage: (page: string) => void;
  setTheme: (theme: 'light' | 'dark') => void;

  // Sources panel actions
  openSourcesPanel: (sources: SourceDocument[]) => void;
  closeSourcesPanel: () => void;

  // Document viewer actions
  openDocumentViewer: (documentId: string, documentName: string, highlights: string[], chunks?: ChunkRef[]) => void;
  closeDocumentViewer: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  currentPage: 'chat',
  theme: 'light',

  isSourcesPanelOpen: false,
  activeMessageSources: [],

  activeDocumentViewer: {
    isOpen: false,
    documentId: '',
    documentName: '',
    highlights: [],
    chunks: [],
  },

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setTheme: (theme) => set({ theme }),

  openSourcesPanel: (sources) =>
    set({ isSourcesPanelOpen: true, activeMessageSources: sources }),
  closeSourcesPanel: () =>
    set({ isSourcesPanelOpen: false, activeMessageSources: [] }),

  openDocumentViewer: (documentId, documentName, highlights, chunks) =>
    set({
      activeDocumentViewer: {
        isOpen: true,
        documentId,
        documentName,
        highlights,
        chunks: chunks || [],
      },
    }),
  closeDocumentViewer: () =>
    set({
      activeDocumentViewer: {
        isOpen: false,
        documentId: '',
        documentName: '',
        highlights: [],
        chunks: [],
      },
    }),
}));
