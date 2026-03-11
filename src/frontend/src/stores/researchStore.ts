import { create } from 'zustand';
import { researchAPI } from '../api/endpoints/research';
import type { ResearchSession } from '../types/research';

interface ResearchState {
  session: ResearchSession | null;
  isLoading: boolean;
  error: string | null;

  startResearch: (query: string, projectId: string) => Promise<void>;
  continueResearch: (projectId: string) => Promise<void>;
  concludeResearch: (projectId: string) => Promise<void>;
  fetchSession: (sessionId: string, projectId: string) => Promise<void>;
  clearSession: () => void;
  clearError: () => void;
}

export const useResearchStore = create<ResearchState>((set, get) => ({
  session: null,
  isLoading: false,
  error: null,

  startResearch: async (query, projectId) => {
    set({ isLoading: true, error: null });
    try {
      const session = await researchAPI.start(query, projectId);
      set({ session, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  continueResearch: async (projectId) => {
    const { session } = get();
    if (!session) return;
    set({ isLoading: true, error: null });
    try {
      const updated = await researchAPI.continue(session.id, projectId);
      set({ session: updated, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  concludeResearch: async (projectId) => {
    const { session } = get();
    if (!session) return;
    set({ isLoading: true, error: null });
    try {
      const updated = await researchAPI.conclude(session.id, projectId);
      set({ session: updated, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  fetchSession: async (sessionId, projectId) => {
    set({ isLoading: true, error: null });
    try {
      const session = await researchAPI.getSession(sessionId, projectId);
      set({ session, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  clearSession: () => set({ session: null, error: null }),
  clearError: () => set({ error: null }),
}));
