import { create } from 'zustand';
import { wikiAPI } from '../api/endpoints/wiki';
import { projectAPI } from '../api/endpoints/project';
import type { WikiStructure, WikiPage, WikiDiagnosticResponse } from '../types/wiki';
import type { JobStatus } from '../api/types';

interface WikiState {
  wiki: WikiStructure | null;
  currentPageId: string | null;
  isGenerating: boolean;
  generationJobId: string | null;
  generationStatus: JobStatus | null;
  diagnostic: WikiDiagnosticResponse | null;
  loading: boolean;
  error: string | null;

  fetchWiki: (projectId: string) => Promise<void>;
  generateWiki: (projectId: string) => Promise<void>;
  regenerateWiki: (projectId: string) => Promise<void>;
  fetchDiagnostic: (projectId: string) => Promise<void>;
  pollJobStatus: (jobId: string, projectId: string) => void;
  restoreWikiJob: (projectId: string) => Promise<void>;
  setCurrentPage: (pageId: string | null) => void;
  invalidateWiki: (projectId: string) => Promise<void>;
  clearError: () => void;
}

export const useWikiStore = create<WikiState>((set, get) => ({
  wiki: null,
  currentPageId: null,
  isGenerating: false,
  generationJobId: null,
  generationStatus: null,
  diagnostic: null,
  loading: false,
  error: null,

  fetchWiki: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const wiki = await wikiAPI.getWiki(projectId);
      set({ wiki, loading: false });
    } catch (e) {
      const msg = (e as Error).message;
      set({ loading: false, error: msg });
      // 404 时自动拉取诊断信息
      if (msg.includes('404') || msg.includes('not found') || msg.includes('Not Found')) {
        get().fetchDiagnostic(projectId);
      }
    }
  },

  generateWiki: async (projectId) => {
    set({ isGenerating: true, error: null });
    try {
      const res = await wikiAPI.generate(projectId);
      const jobId = res.job_id;
      localStorage.setItem(`wiki-job:${projectId}`, jobId);
      set({ generationJobId: jobId });
      get().pollJobStatus(jobId, projectId);
    } catch (e) {
      set({ isGenerating: false, error: (e as Error).message });
    }
  },

  regenerateWiki: async (projectId) => {
    set({ isGenerating: true, error: null, diagnostic: null });
    try {
      const res = await wikiAPI.generate(projectId, true);
      const jobId = res.job_id;
      localStorage.setItem(`wiki-job:${projectId}`, jobId);
      set({ generationJobId: jobId, wiki: null });
      get().pollJobStatus(jobId, projectId);
    } catch (e) {
      set({ isGenerating: false, error: (e as Error).message });
    }
  },

  fetchDiagnostic: async (projectId) => {
    try {
      const diag = await wikiAPI.diagnose(projectId);
      set({ diagnostic: diag });
    } catch {
      // 诊断失败不阻塞主流程
    }
  },

  pollJobStatus: (jobId, projectId) => {
    const MAX_POLL_MS = 10 * 60 * 1000; // 10 分钟超时
    const startTime = Date.now();
    const poll = async () => {
      try {
        if (Date.now() - startTime > MAX_POLL_MS) {
          localStorage.removeItem(`wiki-job:${projectId}`);
          set({
            isGenerating: false,
            generationJobId: null,
            generationStatus: null,
            error: 'Wiki 生成超时，请稍后重试',
          });
          return;
        }
        const status = await projectAPI.getJobStatus(jobId);
        set({ generationStatus: status });

        if (status.status === 'pending' || status.status === 'running') {
          setTimeout(poll, 2000);
        } else {
          localStorage.removeItem(`wiki-job:${projectId}`);
          set({ isGenerating: false, generationJobId: null, generationStatus: null });
          if (status.status === 'completed') {
            get().fetchWiki(projectId);
          } else if (status.status === 'failed') {
            set({ error: status.error || 'Wiki 生成失败' });
          }
        }
      } catch {
        localStorage.removeItem(`wiki-job:${projectId}`);
        set({ isGenerating: false, generationJobId: null, generationStatus: null });
      }
    };
    poll();
  },

  restoreWikiJob: async (projectId) => {
    // 第一层：localStorage
    const savedJobId = localStorage.getItem(`wiki-job:${projectId}`);
    if (savedJobId) {
      try {
        const status = await projectAPI.getJobStatus(savedJobId);
        if (status.status === 'pending' || status.status === 'running') {
          set({ isGenerating: true, generationJobId: savedJobId, generationStatus: status });
          get().pollJobStatus(savedJobId, projectId);
          return;
        }
        localStorage.removeItem(`wiki-job:${projectId}`);
      } catch {
        localStorage.removeItem(`wiki-job:${projectId}`);
      }
    }

    // 第二层：后端兜底
    const activeJob = await wikiAPI.getActiveJob(projectId);
    if (activeJob) {
      localStorage.setItem(`wiki-job:${projectId}`, activeJob.job_id);
      set({ isGenerating: true, generationJobId: activeJob.job_id });
      get().pollJobStatus(activeJob.job_id, projectId);
      return;
    }

    // 无活跃任务，加载已有 wiki
    await get().fetchWiki(projectId);
  },

  setCurrentPage: (pageId) => set({ currentPageId: pageId }),

  invalidateWiki: async (projectId) => {
    try {
      await wikiAPI.invalidate(projectId);
      set({ wiki: null, currentPageId: null });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));
