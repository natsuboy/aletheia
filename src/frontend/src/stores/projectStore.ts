import { create } from 'zustand';
import { Project, JobStatus } from '../api/types';
import { projectAPI } from '../api';

const DELETE_JOB_PREFIX = 'delete_job:';

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  indexingJobs: Map<string, JobStatus>;
  deletingJobs: Map<string, string>; // projectId → jobId
  exitingProjects: Set<string>; // projectId 正在退出动画

  fetchProjects: () => Promise<void>;
  setCurrentProject: (project: Project | null) => void;
  pollJobStatus: (jobId: string) => Promise<void>;
  restoreActiveJobs: () => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  pollDeleteJob: (projectId: string, jobId: string) => Promise<void>;
  clearError: () => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,
  indexingJobs: new Map(),
  deletingJobs: new Map(),
  exitingProjects: new Set(),

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await projectAPI.getProjects();
      set({ projects, loading: false });

      // 恢复未完成的删除轮询
      const { deletingJobs } = get();
      for (const [projectId, jobId] of deletingJobs.entries()) {
        get().pollDeleteJob(projectId, jobId);
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : '获取项目列表失败',
        loading: false,
      });
    }
  },

  setCurrentProject: (project) => {
    set({ currentProject: project });
  },

  pollJobStatus: async (jobId) => {
    try {
      const status = await projectAPI.getJobStatus(jobId);
      const { indexingJobs } = get();
      indexingJobs.set(jobId, status);
      set({ indexingJobs: new Map(indexingJobs) });

      if (status.status === 'pending' || status.status === 'running') {
        setTimeout(() => get().pollJobStatus(jobId), 2000);
      } else {
        localStorage.removeItem(`job:${jobId}`);
        if (status.status === 'completed') {
          await get().fetchProjects();
        }
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : '获取任务状态失败',
      });
    }
  },

  restoreActiveJobs: async () => {
    // 恢复摄取任务
    const jobIds = Object.keys(localStorage)
      .filter((k) => k.startsWith('job:'))
      .map((k) => localStorage.getItem(k)!);
    for (const jobId of jobIds) {
      try {
        const status = await projectAPI.getJobStatus(jobId);
        if (status.status === 'pending' || status.status === 'running') {
          const { indexingJobs } = get();
          indexingJobs.set(jobId, status);
          set({ indexingJobs: new Map(indexingJobs) });
          get().pollJobStatus(jobId);
        } else {
          localStorage.removeItem(`job:${jobId}`);
        }
      } catch {
        localStorage.removeItem(`job:${jobId}`);
      }
    }

    // 恢复删除任务
    const deleteEntries = Object.keys(localStorage)
      .filter((k) => k.startsWith(DELETE_JOB_PREFIX));
    for (const key of deleteEntries) {
      const projectId = key.slice(DELETE_JOB_PREFIX.length);
      const jobId = localStorage.getItem(key)!;
      const { deletingJobs } = get();
      deletingJobs.set(projectId, jobId);
      set({ deletingJobs: new Map(deletingJobs) });
      get().pollDeleteJob(projectId, jobId);
    }
  },

  deleteProject: async (projectId) => {
    try {
      const { job_id } = await projectAPI.deleteProject(projectId);
      // 记录删除中状态
      localStorage.setItem(`${DELETE_JOB_PREFIX}${projectId}`, job_id);
      const { deletingJobs } = get();
      deletingJobs.set(projectId, job_id);
      set({ deletingJobs: new Map(deletingJobs) });
      get().pollDeleteJob(projectId, job_id);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : '删除项目失败',
      });
      throw error;
    }
  },

  pollDeleteJob: async (projectId, jobId) => {
    try {
      const status = await projectAPI.getJobStatus(jobId);

      if (status.status === 'pending' || status.status === 'running') {
        setTimeout(() => get().pollDeleteJob(projectId, jobId), 2000);
        return;
      }

      // 任务结束，清理 localStorage 和 deletingJobs
      localStorage.removeItem(`${DELETE_JOB_PREFIX}${projectId}`);
      const { deletingJobs } = get();
      deletingJobs.delete(projectId);
      set({ deletingJobs: new Map(deletingJobs) });

      if (status.status === 'completed') {
        // 触发退出动画
        const { exitingProjects } = get();
        exitingProjects.add(projectId);
        set({ exitingProjects: new Set(exitingProjects) });

        // 动画结束后移除项目
        setTimeout(() => {
          const { projects, currentProject, exitingProjects: ep } = get();
          ep.delete(projectId);
          set({
            projects: projects.filter((p) => p.id !== projectId),
            currentProject: currentProject?.id === projectId ? null : currentProject,
            exitingProjects: new Set(ep),
          });
        }, 350);
      } else {
        // 失败：恢复正常状态，显示错误
        set({ error: status.message || '删除失败，请重试' });
      }
    } catch {
      // 网络错误，稍后重试
      setTimeout(() => get().pollDeleteJob(projectId, jobId), 3000);
    }
  },

  clearError: () => set({ error: null }),
}));
