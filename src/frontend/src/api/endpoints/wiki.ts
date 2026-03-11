import { apiClient } from '../client';
import type {
  WikiStructure,
  WikiPage,
  WikiGenerateResponse,
  WikiExportResponse,
  WikiDiagnosticResponse,
} from '../../types/wiki';

export const wikiAPI = {
  async generate(projectId: string, force = false): Promise<WikiGenerateResponse> {
    return apiClient.post<WikiGenerateResponse>('/api/wiki/generate', {
      project_id: projectId,
      force,
    });
  },

  async getActiveJob(projectId: string): Promise<WikiGenerateResponse | null> {
    try {
      return await apiClient.get<WikiGenerateResponse>(
        `/api/wiki/generate/active/${projectId}`
      );
    } catch {
      return null; // 404 = 无活跃任务
    }
  },

  async getWiki(projectId: string): Promise<WikiStructure> {
    return apiClient.get<WikiStructure>(`/api/wiki/${projectId}`);
  },

  async getPage(projectId: string, pageId: string): Promise<WikiPage> {
    return apiClient.get<WikiPage>(`/api/wiki/${projectId}/page/${pageId}`);
  },

  async invalidate(projectId: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(`/api/wiki/${projectId}`);
  },

  async diagnose(projectId: string): Promise<WikiDiagnosticResponse> {
    return apiClient.get<WikiDiagnosticResponse>(
      `/api/wiki/diagnose/${projectId}`
    );
  },

  async exportWiki(
    projectId: string,
    format: 'markdown' | 'json' = 'markdown',
  ): Promise<WikiExportResponse> {
    return apiClient.post<WikiExportResponse>('/api/wiki/export', {
      project_id: projectId,
      format,
    });
  },
};
