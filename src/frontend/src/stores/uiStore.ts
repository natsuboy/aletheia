import { create } from 'zustand';
import type { ViewMode, RightPanelTab, CodeReference, CodeReferenceFocus } from '../types/graph';

interface UIStore {
  // Layout
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  viewMode: ViewMode;

  // Panels
  isFileTreeOpen: boolean;
  isRightPanelOpen: boolean;
  rightPanelTab: RightPanelTab;
  isCodePanelOpen: boolean;

  // Code references (AI citations + user selections)
  codeReferences: CodeReference[];
  codeReferenceFocus: CodeReferenceFocus | null;
  operationTimeline: Array<{
    id: string;
    kind: 'endpoint' | 'references' | 'chat' | 'file' | 'node';
    label: string;
    timestamp: number;
  }>;

  // Actions — layout
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setViewMode: (mode: ViewMode) => void;

  // Actions — panels
  toggleFileTree: () => void;
  toggleRightPanel: () => void;
  setRightPanelTab: (tab: RightPanelTab) => void;
  toggleCodePanel: () => void;
  setCodePanelOpen: (open: boolean) => void;

  // Actions — code references
  addCodeReference: (ref: CodeReference) => void;
  removeCodeReference: (id: string) => void;
  clearAICodeReferences: () => void;
  clearCodeReferences: () => void;
  focusCodeReference: (referenceId: string) => void;
  addOperation: (op: {
    kind: 'endpoint' | 'references' | 'chat' | 'file' | 'node';
    label: string;
  }) => void;
}

export const useUIStore = create<UIStore>((set, get) => ({
  sidebarOpen: true,
  theme: 'dark',
  viewMode: 'onboarding',

  isFileTreeOpen: true,
  isRightPanelOpen: false,
  rightPanelTab: 'chat',
  isCodePanelOpen: false,

  codeReferences: [],
  codeReferenceFocus: null,
  operationTimeline: [],

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
  setViewMode: (viewMode) => set({ viewMode }),

  toggleFileTree: () => set((s) => ({ isFileTreeOpen: !s.isFileTreeOpen })),
  toggleRightPanel: () => set((s) => ({ isRightPanelOpen: !s.isRightPanelOpen })),
  setRightPanelTab: (tab) => set({ rightPanelTab: tab, isRightPanelOpen: true }),
  toggleCodePanel: () => set((s) => ({ isCodePanelOpen: !s.isCodePanelOpen })),
  setCodePanelOpen: (open) => set({ isCodePanelOpen: open }),

  addCodeReference: (ref) => {
    const { codeReferences } = get();
    // Avoid duplicates by filePath + startLine
    const exists = codeReferences.some(
      (r) => r.filePath === ref.filePath && r.startLine === ref.startLine,
    );
    if (!exists) {
      set({
        codeReferences: [...codeReferences, ref],
        isCodePanelOpen: true,
      });
    }
  },

  removeCodeReference: (id) =>
    set((s) => ({
      codeReferences: s.codeReferences.filter((r) => r.id !== id),
      isCodePanelOpen: s.codeReferences.length > 1,
    })),

  clearAICodeReferences: () =>
    set((s) => ({
      codeReferences: s.codeReferences.filter((r) => r.source !== 'ai'),
    })),

  clearCodeReferences: () => set({ codeReferences: [], isCodePanelOpen: false }),

  focusCodeReference: (referenceId) =>
    set({ codeReferenceFocus: { referenceId, ts: Date.now() } }),

  addOperation: ({ kind, label }) =>
    set((s) => ({
      operationTimeline: [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          kind,
          label,
          timestamp: Date.now(),
        },
        ...s.operationTimeline,
      ].slice(0, 30),
    })),
}));
